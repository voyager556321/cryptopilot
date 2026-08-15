"""Unit tests for action-plan backtest (no network)."""

from __future__ import annotations

from datetime import date, timedelta

from src.portfolio.backtest.data import DailySnapshot
from src.portfolio.backtest.metrics import compute_metrics, max_drawdown
from src.portfolio.backtest.runner import run_action_plan_backtest
from src.portfolio.backtest.journal import summarize_action_forwards


def _bars(n: int = 90, start: date | None = None):
    start = start or date(2026, 5, 1)
    out = []
    px = 60_000.0
    for i in range(n):
        d = start + timedelta(days=i)
        # gentle uptrend with a dip in the middle
        if 40 <= i < 55:
            px *= 0.99
        else:
            px *= 1.002
        out.append({
            "ts": i,
            "date": d.isoformat(),
            "open": px,
            "high": px * 1.01,
            "low": px * 0.99,
            "close": px,
        })
    return out


def _snaps(n: int = 20, start: date | None = None):
    start = start or date(2026, 7, 1)
    out = []
    eq = 5000.0
    for i in range(n):
        d = start + timedelta(days=i)
        eq *= 1.001 if i % 3 else 0.998
        out.append(
            DailySnapshot(
                date=d.isoformat(),
                timestamp=f"{d.isoformat()}T12:00:00+00:00",
                total_usdt=eq,
                btc_eth_pct=50.0,
                stable_pct=15.0,
                alts_pct=35.0,
            )
        )
    return out


def test_max_drawdown_simple():
    assert abs(max_drawdown([100, 110, 88, 95]) - (88 / 110 - 1)) < 1e-9


def test_backtest_runs_same_engine_modes():
    # Align snaps with bars so cycle has data
    start = date(2026, 6, 1)
    bars = _bars(100, start=date(2026, 4, 1))
    snaps = _snaps(25, start=start)
    result = run_action_plan_backtest(snaps, btc_bars=bars, execute_locks=True)
    assert result.meta["days"] == 25
    assert len(result.journal) == 25
    assert set(result.equity.keys()) == {"lockin", "buy_hold", "usdt_heavy"}
    names = {s["name"] for s in result.metrics["strategies"]}
    assert names == {"lockin", "buy_hold", "usdt_heavy"}
    # Every journal row has required fields
    row = result.journal[10]
    for key in (
        "date",
        "portfolio_value",
        "daily_pnl",
        "btc_regime",
        "usdt_percent",
        "action",
        "reason",
        "amount_to_lock",
        "forward",
    ):
        assert key in row
    assert "ret_1d" in row["forward"]


def test_metrics_and_forward_summary():
    m = compute_metrics("t", [100.0, 110.0, 105.0], profit_locks=2, locked_usdt_total=30)
    assert m.total_return == 0.05
    assert m.profit_locks == 2
    summary = summarize_action_forwards([
        {"action": "PROFIT_LOCK", "forward": {"ret_1d": -0.01, "ret_3d": -0.02, "ret_7d": 0.01}},
        {"action": "PROFIT_LOCK", "forward": {"ret_1d": 0.01, "ret_3d": -0.01, "ret_7d": -0.02}},
        {"action": "HOLD", "forward": {"ret_1d": 0.0, "ret_3d": 0.02, "ret_7d": 0.03}},
    ])
    assert summary["PROFIT_LOCK"]["count"] == 2
    assert summary["PROFIT_LOCK"]["pct_down_3d"] == 1.0
