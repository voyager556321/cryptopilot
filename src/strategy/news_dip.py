"""News + dip / bear-sell alert rules (alert-only, no order execution)."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Sequence

from src.config import NewsDipConfig
from src.news.fetch import NewsItem
from src.news.sentiment import SentimentResult, classify_item


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    high: float
    low: float
    dip_pct: float  # positive number meaning % below high
    bounce_from_low_pct: float
    volume_ratio: float
    change_24h_pct: Optional[float] = None


@dataclass
class AlertSignal:
    timestamp: str
    symbol: str
    action: str  # ALERT | ALERT_SHORT | WATCH | SKIP
    news_title: str
    news_url: str
    news_source: str
    sentiment: str
    confidence: str
    category: str
    price: float
    dip_pct: float
    bounce_from_low_pct: float
    volume_ratio: float
    suggested_size_usdt: float
    take_profit_pct: float
    stop_loss_pct: float
    time_stop_hours: int
    skip_reason: str
    rationale: str
    side: str = "long"  # long | short
    strategy: str = "news_dip"  # news_dip | news_bear | rebalance

    def to_dict(self) -> dict:
        return asdict(self)


class NewsDipStrategy:
    """Bull news+dip longs and optional bear/treasury-sell shorts."""

    def __init__(self, config: NewsDipConfig, *, domain: str = "crypto"):
        self.config = config
        self.domain = domain
        self._last_alert_at: Dict[str, datetime] = {}

    def evaluate(
        self,
        news_items: Sequence[NewsItem],
        markets: Dict[str, MarketSnapshot],
        now: Optional[datetime] = None,
    ) -> List[AlertSignal]:
        now = now or datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self.config.news_window_minutes)
        signals: List[AlertSignal] = []

        for item in news_items:
            published = item.published
            if published is not None:
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if published < window_start:
                    continue

            sentiment = classify_item(item, self.config.symbols, domain=self.domain)
            # Equity: only alert on news that matched a holding (avoid spraying all tickers)
            if self.domain == "equity":
                targets = sentiment.assets
                if not targets:
                    continue
            else:
                targets = sentiment.assets or list(self.config.symbols)

            for symbol in targets:
                if symbol not in markets:
                    signals.append(self._skip(
                        item, sentiment, symbol, markets.get(symbol),
                        "unknown_or_missing_market", now
                    ))
                    continue

                market = markets[symbol]
                signal = self._evaluate_one(item, sentiment, market, now)
                if signal is not None:
                    signals.append(signal)

        return signals

    def _cooldown_key(self, symbol: str, side: str) -> str:
        return f"{symbol}:{side}"

    def _evaluate_one(
        self,
        item: NewsItem,
        sentiment: SentimentResult,
        market: MarketSnapshot,
        now: datetime,
    ) -> Optional[AlertSignal]:
        # Prefer bear/treasury path when clearly bearish
        if self.config.enable_bear_alerts and (
            sentiment.sentiment == "bear" or sentiment.category == "treasury_sell"
        ):
            return self._evaluate_bear(item, sentiment, market, now)

        if sentiment.sentiment == "bull":
            return self._evaluate_bull_dip(item, sentiment, market, now)

        return self._skip(item, sentiment, market.symbol, market, "not_actionable_sentiment", now)

    def _evaluate_bull_dip(
        self,
        item: NewsItem,
        sentiment: SentimentResult,
        market: MarketSnapshot,
        now: datetime,
    ) -> AlertSignal:
        cfg = self.config

        if cfg.require_high_confidence and sentiment.confidence != "high":
            return self._skip(item, sentiment, market.symbol, market, "low_confidence", now)

        if sentiment.category == "hack" and self.domain != "equity":
            return self._skip(item, sentiment, market.symbol, market, "hack_category_block", now)

        key = self._cooldown_key(market.symbol, "long")
        last = self._last_alert_at.get(key)
        if last and (now - last) < timedelta(minutes=cfg.signal_cooldown_minutes):
            return self._skip(item, sentiment, market.symbol, market, "cooldown", now)

        if market.volume_ratio < cfg.volume_ratio_min:
            return self._skip(item, sentiment, market.symbol, market, "low_volume", now)

        if market.dip_pct < cfg.dip_min_pct:
            return self._skip(item, sentiment, market.symbol, market, "dip_too_shallow", now)

        if market.dip_pct > cfg.dip_max_pct:
            return self._skip(item, sentiment, market.symbol, market, "dip_too_deep", now)

        if market.bounce_from_low_pct >= cfg.late_move_pct:
            return self._skip(item, sentiment, market.symbol, market, "late_move", now)

        size = cfg.bank_usdt * cfg.risk_per_alert_pct
        self._last_alert_at[key] = now

        return AlertSignal(
            timestamp=now.isoformat(timespec="seconds"),
            symbol=market.symbol,
            action="ALERT",
            news_title=item.title,
            news_url=item.url,
            news_source=item.source,
            sentiment=sentiment.sentiment,
            confidence=sentiment.confidence,
            category=sentiment.category,
            price=market.price,
            dip_pct=market.dip_pct,
            bounce_from_low_pct=market.bounce_from_low_pct,
            volume_ratio=market.volume_ratio,
            suggested_size_usdt=round(size, 2),
            take_profit_pct=cfg.take_profit_pct,
            stop_loss_pct=cfg.stop_loss_pct,
            time_stop_hours=cfg.time_stop_hours,
            skip_reason="",
            rationale=sentiment.rationale,
            side="long",
            strategy="news_dip",
        )

    def _evaluate_bear(
        self,
        item: NewsItem,
        sentiment: SentimentResult,
        market: MarketSnapshot,
        now: datetime,
    ) -> AlertSignal:
        cfg = self.config

        if cfg.require_high_confidence and sentiment.confidence != "high":
            return self._skip(item, sentiment, market.symbol, market, "low_confidence", now)

        key = self._cooldown_key(market.symbol, "short")
        last = self._last_alert_at.get(key)
        if last and (now - last) < timedelta(minutes=cfg.signal_cooldown_minutes):
            return self._skip(item, sentiment, market.symbol, market, "cooldown", now)

        # If already dumped hard, likely priced in → WATCH only
        ch = market.change_24h_pct
        if ch is not None and ch <= -cfg.bear_late_move_pct:
            return AlertSignal(
                timestamp=now.isoformat(timespec="seconds"),
                symbol=market.symbol,
                action="WATCH",
                news_title=item.title,
                news_url=item.url,
                news_source=item.source,
                sentiment=sentiment.sentiment,
                confidence=sentiment.confidence,
                category=sentiment.category,
                price=market.price,
                dip_pct=market.dip_pct,
                bounce_from_low_pct=market.bounce_from_low_pct,
                volume_ratio=market.volume_ratio,
                suggested_size_usdt=0.0,
                take_profit_pct=cfg.take_profit_pct,
                stop_loss_pct=cfg.stop_loss_pct,
                time_stop_hours=cfg.time_stop_hours,
                skip_reason="already_down_24h_priced_in",
                rationale=f"{sentiment.rationale}; 24h={ch:.2%} → watch only",
                side="short",
                strategy="news_bear",
            )

        size = cfg.bank_usdt * cfg.risk_per_alert_pct
        self._last_alert_at[key] = now

        return AlertSignal(
            timestamp=now.isoformat(timespec="seconds"),
            symbol=market.symbol,
            action="ALERT_SHORT",
            news_title=item.title,
            news_url=item.url,
            news_source=item.source,
            sentiment="bear",
            confidence=sentiment.confidence,
            category=sentiment.category,
            price=market.price,
            dip_pct=market.dip_pct,
            bounce_from_low_pct=market.bounce_from_low_pct,
            volume_ratio=market.volume_ratio,
            suggested_size_usdt=round(size, 2),
            take_profit_pct=cfg.take_profit_pct,
            stop_loss_pct=cfg.stop_loss_pct,
            time_stop_hours=cfg.time_stop_hours,
            skip_reason="",
            rationale=sentiment.rationale,
            side="short",
            strategy="news_bear",
        )

    def _skip(
        self,
        item: NewsItem,
        sentiment: SentimentResult,
        symbol: str,
        market: Optional[MarketSnapshot],
        reason: str,
        now: datetime,
    ) -> AlertSignal:
        return AlertSignal(
            timestamp=now.isoformat(timespec="seconds"),
            symbol=symbol,
            action="SKIP",
            news_title=item.title,
            news_url=item.url,
            news_source=item.source,
            sentiment=sentiment.sentiment,
            confidence=sentiment.confidence,
            category=sentiment.category,
            price=market.price if market else 0.0,
            dip_pct=market.dip_pct if market else 0.0,
            bounce_from_low_pct=market.bounce_from_low_pct if market else 0.0,
            volume_ratio=market.volume_ratio if market else 0.0,
            suggested_size_usdt=0.0,
            take_profit_pct=self.config.take_profit_pct,
            stop_loss_pct=self.config.stop_loss_pct,
            time_stop_hours=self.config.time_stop_hours,
            skip_reason=reason,
            rationale=sentiment.rationale,
            side="flat",
            strategy="news",
        )
