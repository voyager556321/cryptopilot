"""IBKR equity news+dip alerts (advice only, Yahoo Finance, no orders)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import NewsDipConfig
from src.news.equity_fetch import fetch_yahoo_markets, fetch_yahoo_news_for_symbols
from src.news.sentiment import classify_many
from src.strategy.news_dip import NewsDipStrategy


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _empty_state() -> dict:
    return {
        "last_run": None,
        "symbols": [],
        "news": [],
        "markets": {},
        "alerts": [],
        "error": None,
        "note": "Equity news+dip via Yahoo — advice only, no orders.",
    }


class IbkrNewsAlerts:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "ibkr_news_state.json"
        self._strategy: Optional[NewsDipStrategy] = None

    def load(self) -> dict:
        if not self.path.exists():
            return _empty_state()
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _empty_state()
            return {**_empty_state(), **data}
        except Exception:
            return _empty_state()

    def _save(self, state: dict) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def _build_config(self, symbols: List[str], bank_usd: float) -> NewsDipConfig:
        return NewsDipConfig(
            enabled=True,
            symbols=symbols,
            quote="USD",
            news_sources=["yahoo"],
            news_window_minutes=24 * 60,  # stocks move slower; keep day of headlines
            poll_interval_seconds=300,
            dip_lookback_hours=24,
            dip_min_pct=0.015,   # 1.5%
            dip_max_pct=0.06,    # 6%
            volume_ratio_min=0.4,
            late_move_pct=0.035,
            take_profit_pct=0.03,
            stop_loss_pct=0.02,
            time_stop_hours=48,
            risk_per_alert_pct=0.02,
            bank_usdt=max(50.0, float(bank_usd or 250)),
            signal_cooldown_minutes=180,
            require_high_confidence=True,
            ohlcv_timeframe="1h",
            ohlcv_limit=48,
            enable_bear_alerts=True,
            bear_late_move_pct=0.03,
        )

    def run_once(self, snapshot: dict) -> dict:
        """Fetch Yahoo news + OHLCV for IBKR holdings and evaluate alerts."""
        holdings = snapshot.get("holdings") or []
        symbols = sorted({
            str(h.get("symbol") or "").upper()
            for h in holdings
            if h.get("symbol")
        })
        if not symbols:
            state = {
                **_empty_state(),
                "last_run": _utcnow().isoformat(timespec="seconds"),
                "error": "No IBKR holdings to scan",
            }
            self._save(state)
            return state

        bank = float(snapshot.get("total_usd") or 250)
        cfg = self._build_config(symbols, bank)
        if self._strategy is None or self._strategy.config.symbols != symbols:
            self._strategy = NewsDipStrategy(cfg, domain="equity")
        else:
            self._strategy.config = cfg

        error = None
        news_items: List = []
        markets: Dict = {}
        try:
            news_items = fetch_yahoo_news_for_symbols(symbols)
            markets = fetch_yahoo_markets(symbols, lookback_hours=cfg.dip_lookback_hours)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        news_payload = classify_many(news_items, symbols, domain="equity") if news_items else []
        signals = []
        if news_items and markets and self._strategy:
            try:
                signals = self._strategy.evaluate(news_items, markets)
            except Exception as e:
                error = (error + "; " if error else "") + f"evaluate: {type(e).__name__}: {e}"

        actionable = [
            s.to_dict() for s in signals
            if s.action in ("ALERT", "ALERT_SHORT", "WATCH")
        ]

        markets_payload = {
            sym: {
                "symbol": m.symbol,
                "price": round(m.price, 4),
                "high": round(m.high, 4),
                "low": round(m.low, 4),
                "dip_pct": round(m.dip_pct, 4),
                "bounce_from_low_pct": round(m.bounce_from_low_pct, 4),
                "volume_ratio": round(m.volume_ratio, 3),
                "change_24h_pct": None if m.change_24h_pct is None else round(m.change_24h_pct, 4),
            }
            for sym, m in markets.items()
        }

        state = {
            "last_run": _utcnow().isoformat(timespec="seconds"),
            "symbols": symbols,
            "news": news_payload[:40],
            "markets": markets_payload,
            "alerts": actionable[:40],
            "error": error,
            "note": (
                "Equity news+dip (Yahoo) — ALERT=dip buy idea, "
                "ALERT_SHORT=trim idea, WATCH=priced-in. No orders."
            ),
            "stats": {
                "news_count": len(news_payload),
                "markets_count": len(markets_payload),
                "alert_count": sum(1 for a in actionable if a.get("action") in ("ALERT", "ALERT_SHORT", "WATCH")),
            },
        }
        self._save(state)
        return state


def get_cached_or_run(
    store: IbkrNewsAlerts,
    snapshot: dict,
    *,
    force: bool = False,
    max_age_seconds: int = 300,
) -> dict:
    """Return cached state unless stale / forced / missing."""
    state = store.load()
    if not force and state.get("last_run") and not state.get("error"):
        try:
            last = datetime.fromisoformat(state["last_run"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            age = (_utcnow() - last).total_seconds()
            if age < max_age_seconds and state.get("symbols"):
                return state
        except Exception:
            pass
    if not snapshot.get("available"):
        return {
            **_empty_state(),
            "error": snapshot.get("message") or "IBKR snapshot unavailable",
        }
    return store.run_once(snapshot)
