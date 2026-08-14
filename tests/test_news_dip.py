"""Unit tests for rule-based sentiment and news-dip rules."""

from datetime import datetime, timezone, timedelta

from src.config import NewsDipConfig
from src.news.fetch import NewsItem
from src.news.sentiment import classify_item
from src.strategy.news_dip import MarketSnapshot, NewsDipStrategy


def test_classify_bull_bitcoin_etf():
    item = NewsItem(
        title="Bitcoin ETF sees record inflows as institutions buy BTC",
        url="https://example.com/1",
        source="coindesk",
        published=datetime.now(timezone.utc),
        summary="Institutional adoption continues",
    )
    result = classify_item(item, ["BTC", "ETH", "SOL", "ZEC"])
    assert result.sentiment == "bull"
    assert result.confidence == "high"
    assert "BTC" in result.assets


def test_classify_zec_zcash_alias():
    item = NewsItem(
        title="Zcash rally continues as ZEC hits record volume on listing news",
        url="https://example.com/zec",
        source="coindesk",
        published=datetime.now(timezone.utc),
        summary="Institutional interest in privacy coins",
    )
    result = classify_item(item, ["BTC", "ETH", "SOL", "ZEC"])
    assert "ZEC" in result.assets
    assert result.sentiment == "bull"


def test_classify_ethereum_and_solana():
    eth = NewsItem(
        title="Ethereum ETF sees record inflows as ether institutional adoption grows",
        url="https://example.com/eth",
        source="coindesk",
        published=datetime.now(timezone.utc),
        summary="Etherium network upgrade buzz",  # misspelling still maps to ETH
    )
    sol = NewsItem(
        title="Solana partnership launch sparks SOL rally to record",
        url="https://example.com/sol",
        source="cointelegraph",
        published=datetime.now(timezone.utc),
        summary="Solana institutional staking interest",
    )
    eth_r = classify_item(eth, ["BTC", "ETH", "SOL", "ZEC"])
    sol_r = classify_item(sol, ["BTC", "ETH", "SOL", "ZEC"])
    assert "ETH" in eth_r.assets
    assert eth_r.sentiment == "bull"
    assert "SOL" in sol_r.assets
    assert sol_r.sentiment == "bull"
    # short alias must not false-positive on unrelated words
    noise = NewsItem(
        title="Solar ethics solution for hospitals",
        url="https://example.com/noise",
        source="coindesk",
        published=datetime.now(timezone.utc),
        summary="",
    )
    noise_r = classify_item(noise, ["BTC", "ETH", "SOL", "ZEC"])
    assert "SOL" not in noise_r.assets
    assert "ETH" not in noise_r.assets


def test_classify_bear_hack():
    item = NewsItem(
        title="Major exchange hacked, funds stolen",
        url="https://example.com/2",
        source="cointelegraph",
        published=datetime.now(timezone.utc),
        summary="Exploit drains wallets",
    )
    result = classify_item(item, ["BTC", "ETH", "SOL"])
    assert result.sentiment == "bear"
    assert result.category == "hack"


def test_news_dip_alert_on_valid_setup():
    cfg = NewsDipConfig(
        dip_min_pct=0.03,
        dip_max_pct=0.08,
        volume_ratio_min=0.8,
        late_move_pct=0.05,
        require_high_confidence=True,
        signal_cooldown_minutes=0,
        bank_usdt=10000,
        risk_per_alert_pct=0.01,
    )
    strategy = NewsDipStrategy(cfg)
    item = NewsItem(
        title="Ethereum ETF approval sparks bullish inflows",
        url="https://example.com/3",
        source="coindesk",
        published=datetime.now(timezone.utc),
        summary="ETH institutional interest",
    )
    markets = {
        "ETH": MarketSnapshot(
            symbol="ETH",
            price=3000,
            high=3200,
            low=2950,
            dip_pct=0.0625,
            bounce_from_low_pct=0.017,
            volume_ratio=1.2,
        )
    }
    signals = strategy.evaluate([item], markets)
    alerts = [s for s in signals if s.action == "ALERT"]
    assert len(alerts) >= 1
    assert alerts[0].symbol == "ETH"
    assert alerts[0].suggested_size_usdt == 100.0


def test_news_dip_skip_late_move():
    cfg = NewsDipConfig(late_move_pct=0.05, dip_min_pct=0.03, dip_max_pct=0.08)
    strategy = NewsDipStrategy(cfg)
    item = NewsItem(
        title="Solana partnership announcement is bullish",
        url="https://example.com/4",
        source="coindesk",
        published=datetime.now(timezone.utc),
    )
    markets = {
        "SOL": MarketSnapshot(
            symbol="SOL",
            price=150,
            high=160,
            low=130,
            dip_pct=0.0625,
            bounce_from_low_pct=0.15,
            volume_ratio=1.5,
        )
    }
    signals = strategy.evaluate([item], markets)
    assert any(s.skip_reason == "late_move" for s in signals)


def test_news_outside_window_ignored():
    cfg = NewsDipConfig(news_window_minutes=60)
    strategy = NewsDipStrategy(cfg)
    old = NewsItem(
        title="Bitcoin ETF inflows bullish",
        url="https://example.com/5",
        source="coindesk",
        published=datetime.now(timezone.utc) - timedelta(hours=5),
    )
    markets = {
        "BTC": MarketSnapshot(
            symbol="BTC",
            price=90000,
            high=95000,
            low=88000,
            dip_pct=0.05,
            bounce_from_low_pct=0.02,
            volume_ratio=1.0,
        )
    }
    signals = strategy.evaluate([old], markets)
    assert signals == []
