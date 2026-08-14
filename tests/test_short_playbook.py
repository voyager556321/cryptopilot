"""Unattended short-exit playbook (advice only)."""

from datetime import datetime, timezone, timedelta

import pytest

from src.portfolio.short_playbook import (
    ShortWatch,
    build_short_playbook,
    evaluate_position,
    idea_from_alert,
    pick_alert,
    suggested_size_usdt,
)


def test_pick_alert_prefers_btc():
    alerts = [
        {"action": "ALERT_SHORT", "symbol": "ETH", "price": 1800},
        {"action": "ALERT_SHORT", "symbol": "BTC", "price": 60000},
        {"action": "ALERT_SHORT", "symbol": "SOL", "price": 80},
    ]
    picked = pick_alert(alerts)
    assert picked["symbol"] == "BTC"


def test_size_is_1pct_capped():
    assert suggested_size_usdt(5000) == 50.0
    assert suggested_size_usdt(20000) == 100.0


def test_first_try_clears_binance_btc_min():
    from src.portfolio.short_playbook import first_try_notional
    # Error on screen: notional cannot be less than 62.94 = 0.001 BTC
    n = first_try_notional("BTC", 62940, 5000)
    assert n >= 62.94
    assert n < 80


def test_idea_lists_three_exits():
    idea = idea_from_alert(
        {"symbol": "BTC", "price": 100000, "news_title": "bank news"},
        equity_usdt=5000,
    )
    ids = [r["id"] for r in idea["rules"]]
    assert ids == ["stop_loss", "take_profit", "time_stop"]
    assert idea["stop_loss_price"] == 102500
    assert idea["take_profit_price"] == 96000
    # 0.001 BTC min at $100k = $100, so first try is the exchange floor
    assert idea["size_usdt"] == 102.0
    assert idea["leverage"] == 2
    assert idea["not_spot"] is True


def test_evaluate_stop_loss_first():
    opened = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    pos = {
        "id": "abc",
        "opened_at": opened.isoformat(),
        "symbol": "BTC",
        "entry_price": 100000,
        "take_profit_pct": 0.04,
        "stop_loss_pct": 0.025,
        "time_stop_hours": 24,
    }
    ev = evaluate_position(pos, 103000, now=opened + timedelta(hours=1))
    assert ev["status"] == "exit"
    assert ev["exit_reason"] == "stop_loss"
    assert "EXIT NOW" in ev["headline"]


def test_evaluate_take_profit():
    opened = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    pos = {
        "opened_at": opened.isoformat(),
        "symbol": "BTC",
        "entry_price": 100000,
        "take_profit_pct": 0.04,
        "stop_loss_pct": 0.025,
        "time_stop_hours": 24,
    }
    ev = evaluate_position(pos, 95000, now=opened + timedelta(hours=2))
    assert ev["exit_reason"] == "take_profit"


def test_evaluate_time_stop_even_if_flat():
    opened = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    pos = {
        "opened_at": opened.isoformat(),
        "symbol": "BTC",
        "entry_price": 100000,
        "take_profit_pct": 0.04,
        "stop_loss_pct": 0.025,
        "time_stop_hours": 24,
    }
    ev = evaluate_position(pos, 100200, now=opened + timedelta(hours=24, minutes=1))
    assert ev["exit_reason"] == "time_stop"
    assert ev["status"] == "exit"


def test_evaluate_hold_with_clock():
    opened = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    pos = {
        "opened_at": opened.isoformat(),
        "symbol": "BTC",
        "entry_price": 100000,
        "take_profit_pct": 0.04,
        "stop_loss_pct": 0.025,
        "time_stop_hours": 24,
    }
    ev = evaluate_position(pos, 99500, now=opened + timedelta(hours=6))
    assert ev["status"] == "hold"
    assert ev["remaining_hours"] == 18
    assert "HOLD" in ev["headline"]


def test_playbook_idle_without_news():
    book = build_short_playbook(alerts=[], prices={}, tracked_open=None, equity_usdt=5000)
    assert book["mode"] == "idle"


def test_playbook_skip_when_priced_in():
    book = build_short_playbook(
        alerts=[{"action": "WATCH", "symbol": "BTC", "news_title": "already dumped"}],
        prices={},
        tracked_open=None,
        equity_usdt=5000,
    )
    assert book["mode"] == "skip"
    assert "priced in" in book["headline"].lower() or "already down" in book["headline"].lower()


def test_watch_rejects_second_open(tmp_path):
    w = ShortWatch(tmp_path)
    w.open_one({"symbol": "BTC", "entry_price": 60000, "size_usdt": 50})
    with pytest.raises(ValueError):
        w.open_one({"symbol": "ETH", "entry_price": 1800, "size_usdt": 50})
