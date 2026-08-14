"""Tests for threshold rebalance hints and portfolio history helpers."""

from src.portfolio.rebalance_hints import check_rebalance, rebalance_from_portfolio
from src.portfolio.history import PortfolioHistory


def test_rebalance_no_action_inside_band():
    weights = {k: v for k, v in [
        ("BTC", 28), ("ETH", 20), ("SOL", 8), ("BNB", 6), ("XRP", 3),
        ("LINK", 4), ("AAVE", 4), ("ZEC", 4), ("FIL", 2), ("PAXG", 6), ("USDT", 15),
    ]}
    values = {k: v * 100 for k, v in weights.items()}  # total 10000
    signals, minor = check_rebalance(weights, values, 10000)
    assert signals == []
    assert minor == []


def test_rebalance_actionable_on_large_drift():
    weights = {
        "BTC": 50.0,  # target 28, huge overweight
        "ETH": 10.0,
        "SOL": 5.0,
        "BNB": 5.0,
        "XRP": 2.0,
        "LINK": 2.0,
        "AAVE": 2.0,
        "ZEC": 2.0,
        "FIL": 1.0,
        "PAXG": 4.0,
        "USDT": 17.0,
    }
    total = 10000.0
    values = {k: total * (v / 100) for k, v in weights.items()}
    signals, _minor = check_rebalance(weights, values, total)
    assert any(s["asset"] == "BTC" and s["action"] == "SELL" for s in signals)


def test_rebalance_from_portfolio_payload():
    portfolio = {
        "available": True,
        "total_usdt": 5000,
        "assets": {
            "BTC": {"pct": 40, "value_usdt": 2000},
            "ETH": {"pct": 10, "value_usdt": 500},
            "USDT": {"pct": 50, "value_usdt": 2500},
        },
    }
    view = rebalance_from_portfolio(portfolio)
    assert "policy" in view
    assert "allocation" in view
    assert isinstance(view["actionable"], list)


def test_history_record_and_overview(tmp_path):
    hist = PortfolioHistory(tmp_path)
    hist._min_interval_seconds = 0
    ok = hist.record({
        "available": True,
        "total_usdt": 1000,
        "btc_eth_pct": 50,
        "stable_pct": 20,
        "alts_pct": 30,
    }, force=True)
    assert ok
    hist.record({
        "available": True,
        "total_usdt": 1100,
        "btc_eth_pct": 50,
        "stable_pct": 20,
        "alts_pct": 30,
    }, force=True)
    overview = hist.overview(current_total=1100)
    assert overview["points"] >= 2
    assert overview["current_total"] == 1100
    assert overview["sparkline"]
