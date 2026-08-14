"""Tests for bear/treasury-sell news alerts and paper journal."""

from datetime import datetime, timezone

from src.config import NewsDipConfig
from src.news.fetch import NewsItem
from src.news.sentiment import classify_item
from src.portfolio.paper import PaperJournal
from src.strategy.news_dip import MarketSnapshot, NewsDipStrategy


def test_trump_media_sell_is_bear_treasury():
    item = NewsItem(
        title="Trump Media sells another 2,628 BTC, holdings fall to 4,261 BTC",
        url="https://example.com/trump-btc",
        source="coindesk",
        published=datetime.now(timezone.utc),
        summary="Transferred Bitcoin to Crypto.com",
    )
    result = classify_item(item, ["BTC", "ETH", "SOL"])
    assert result.sentiment == "bear"
    assert "BTC" in result.assets
    assert result.category == "treasury_sell"
    assert result.confidence == "high"


def test_bear_alert_short_when_not_already_dumped():
    cfg = NewsDipConfig(
        enable_bear_alerts=True,
        bear_late_move_pct=0.04,
        require_high_confidence=True,
        signal_cooldown_minutes=0,
        bank_usdt=10000,
        risk_per_alert_pct=0.01,
    )
    strategy = NewsDipStrategy(cfg)
    item = NewsItem(
        title="Trump Media sells another 2,628 BTC, holdings fall",
        url="https://example.com/x",
        source="coindesk",
        published=datetime.now(timezone.utc),
    )
    markets = {
        "BTC": MarketSnapshot(
            symbol="BTC",
            price=100000,
            high=102000,
            low=99000,
            dip_pct=0.02,
            bounce_from_low_pct=0.01,
            volume_ratio=1.0,
            change_24h_pct=-0.01,  # only -1%, not priced in
        )
    }
    signals = strategy.evaluate([item], markets)
    assert any(s.action == "ALERT_SHORT" and s.symbol == "BTC" for s in signals)


def test_bear_watch_when_already_down():
    cfg = NewsDipConfig(enable_bear_alerts=True, bear_late_move_pct=0.04, signal_cooldown_minutes=0)
    strategy = NewsDipStrategy(cfg)
    item = NewsItem(
        title="Company sells bitcoin holdings, transferred to exchange",
        url="https://example.com/y",
        source="cointelegraph",
        published=datetime.now(timezone.utc),
    )
    markets = {
        "BTC": MarketSnapshot(
            symbol="BTC",
            price=95000,
            high=100000,
            low=94000,
            dip_pct=0.05,
            bounce_from_low_pct=0.01,
            volume_ratio=1.2,
            change_24h_pct=-0.06,
        )
    }
    signals = strategy.evaluate([item], markets)
    assert any(s.action == "WATCH" for s in signals)


def test_paper_open_and_mark(tmp_path):
    journal = PaperJournal(tmp_path, bank_usdt=5000, max_open=5)
    opened = journal.open_from_news_alert({
        "action": "ALERT_SHORT",
        "symbol": "BTC",
        "price": 100000,
        "suggested_size_usdt": 100,
        "take_profit_pct": 0.04,
        "stop_loss_pct": 0.025,
        "time_stop_hours": 24,
        "strategy": "news_bear",
        "news_title": "sells btc",
    })
    assert opened is not None
    summary = journal.mark_to_market({"BTC": 98000})  # short profits
    assert summary["open_count"] == 1
    assert summary["open"][0]["unrealized_pnl_usdt"] > 0
