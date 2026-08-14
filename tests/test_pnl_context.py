"""Unit tests for multi-horizon PnL context + drawdown-aware profit-lock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.portfolio.action_plan import build_action_plan, profit_lock_gate
from src.portfolio.history import build_pnl_context


def _ts(now: datetime, days_ago: float) -> str:
    return (now - timedelta(days=days_ago)).replace(microsecond=0).isoformat()


def _series(now: datetime, points: list[tuple[float, float]]) -> list[dict]:
    """points: (days_ago, total_usdt)"""
    return [
        {"timestamp": _ts(now, d), "total_usdt": v}
        for d, v in sorted(points, key=lambda x: -x[0])
    ]


def _portfolio(total: float = 5000.0) -> dict:
    return {
        "available": True,
        "total_usdt": total,
        "stable_pct": 20.0,
        "holdings": [
            {"symbol": "LINK", "value_usdt": 200, "pct": 4},
            {"symbol": "BTC", "value_usdt": 2000, "pct": 40},
            {"symbol": "ETH", "value_usdt": 1000, "pct": 20},
        ],
    }


def test_pnl_context_noise_green_day_inside_deep_drawdown_blocks_lock():
    """+$20 today inside ~−$1000 / −16% 30d drawdown → profit-lock must NOT fire."""
    now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    # Peak 6000 → trough 4900 → today 5020 (+20 vs yesterday 5000)
    series = _series(
        now,
        [
            (29, 6000),
            (20, 5600),
            (10, 5200),
            (5, 4900),
            (2, 4950),
            (1, 5000),
            (0.1, 5020),
        ],
    )
    ctx = build_pnl_context(series, current_total=5020, now=now)
    assert ctx["drawdown"]["in_drawdown"] is True
    assert ctx["h1d"]["abs"] is not None and ctx["h1d"]["abs"] >= 15

    allowed, recovering, reasons = profit_lock_gate(ctx)
    assert allowed is False
    assert recovering is False
    assert any("drawdown" in r.lower() or "skipped" in r.lower() for r in reasons)

    hist = {
        "today_pnl": {"abs": 20.0, "pct": 0.004},
        "pnl_context": ctx,
        "current_total": 5020,
    }
    plan = build_action_plan(_portfolio(5020), hist, already_locked_usdt=0.0)
    assert plan["mode"] != "profit_lock"
    assert plan["pnl_context"]["lock_allowed"] is False
    assert "drawdown" in plan["headline"].lower() or any(
        "drawdown" in c.lower() for c in plan["checklist"]
    )


def test_pnl_context_red_day_in_strong_month_lock_stays_available():
    """−$15 today inside month +$1000, no active DD → gate open (lock available)."""
    now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    # Steady climb 4000 → 5000, small red day to 4985
    series = _series(
        now,
        [
            (29, 4000),
            (20, 4300),
            (10, 4600),
            (5, 4800),
            (2, 4950),
            (1, 5000),
            (0.05, 4985),
        ],
    )
    ctx = build_pnl_context(series, current_total=4985, now=now)
    assert ctx["drawdown"]["in_drawdown"] is False
    assert ctx["h30d"]["abs"] is not None and ctx["h30d"]["abs"] > 500

    allowed, recovering, reasons = profit_lock_gate(ctx)
    assert allowed is True
    assert recovering is False
    assert any("available" in r.lower() for r in reasons)

    hist = {
        "today_pnl": {"abs": -15.0, "pct": -0.003},
        "pnl_context": ctx,
        "current_total": 4985,
    }
    plan = build_action_plan(_portfolio(4985), hist)
    # Negative day → no lock fire, but not blocked by drawdown
    assert plan["mode"] != "profit_lock"
    assert plan["pnl_context"]["lock_allowed"] is True
    assert any("available" in c.lower() for c in plan["checklist"])


def test_pnl_context_recovery_from_trough_allows_profit_lock():
    """Rising several days from trough while still below peak → lock should fire."""
    now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    # Peak 6000, trough 4800, then recovery 4800→5200 (+40 today vs 5160)
    series = _series(
        now,
        [
            (28, 6000),
            (20, 5500),
            (14, 5000),
            (10, 4800),  # trough
            (7, 4900),
            (5, 5000),
            (3, 5100),
            (1, 5160),
            (0.05, 5200),
        ],
    )
    ctx = build_pnl_context(series, current_total=5200, now=now)
    dd = ctx["drawdown"]
    # Still below peak → in drawdown, but bounce from trough ≥ 3% and 7D green
    assert dd["in_drawdown"] is True
    assert dd["bounce_from_30d_low_pct"] is not None
    assert dd["bounce_from_30d_low_pct"] >= 0.03
    assert ctx["h7d"]["abs"] is not None and ctx["h7d"]["abs"] >= 0

    allowed, recovering, reasons = profit_lock_gate(ctx)
    assert allowed is True
    assert recovering is True
    assert any("recovering" in r.lower() for r in reasons)

    hist = {
        "today_pnl": {"abs": 40.0, "pct": 0.0077},
        "pnl_context": ctx,
        "current_total": 5200,
    }
    plan = build_action_plan(_portfolio(5200), hist, already_locked_usdt=0.0)
    assert plan["mode"] == "profit_lock"
    assert plan["suggested_lock_usdt"] > 0
    assert plan["pnl_context"]["recovering"] is True
    assert any("recovering" in c.lower() for c in plan["checklist"])


def test_build_pnl_context_horizons_ready():
    now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    series = _series(now, [(40, 1000), (20, 1100), (5, 1200), (0.1, 1250)])
    ctx = build_pnl_context(series, current_total=1250, now=now)
    assert ctx["h1d"]["ready"] is True
    assert ctx["h7d"]["ready"] is True
    assert ctx["h30d"]["ready"] is True
    # 30d window starts at first point within 30d → day-20 @ 1100
    assert ctx["h30d"]["abs"] == 150.0
    assert ctx["h7d"]["abs"] == 50.0
