"""Tests for relative strength vs BTC + blended asset_risk_score."""

from __future__ import annotations

from src.portfolio.action_plan import build_action_plan
from src.portfolio.relative_strength import (
    build_asset_momentum,
    relative_strength,
    rolling_return,
)


def _ramp(start: float, end: float, n: int = 31) -> list[float]:
    """n bars → return over (n-1) days matches rolling_return(..., n-1)."""
    if n < 2:
        return [end]
    step = (end - start) / (n - 1)
    return [start + i * step for i in range(n)]


def test_rolling_return_and_rs_basic():
    btc = _ramp(100, 110)  # +10% over 30 days
    sol = _ramp(100, 150)  # +50%
    assert abs(rolling_return(btc, 30) - 0.10) < 1e-9
    assert abs(rolling_return(sol, 30) - 0.50) < 1e-9
    rs = relative_strength(sol, btc, 30)
    assert rs is not None and abs(rs - 0.40) < 1e-9


def test_neutral_macro_strong_sol_rs_accumulate():
    """BTC macro=range/neutral, SOL RS ~+40% → accumulate/hold, not reduce."""
    btc = _ramp(100, 102)  # ~flat
    sol = _ramp(100, 142)  # ~+42%
    m = build_asset_momentum("SOL", sol, btc, cycle_mode="range")
    assert m["rs_30d"] is not None and m["rs_30d"] >= 0.30
    assert m["label"] == "accumulate"
    assert "despite" in m["explain"].lower() or m["label"] == "accumulate"

    plan = build_action_plan(
        {
            "available": True,
            "total_usdt": 5000,
            "stable_pct": 20,
            "holdings": [{"symbol": "SOL", "value_usdt": 400, "pct": 8}],
        },
        {"today_pnl": {"abs": 0, "pct": 0}, "pnl_context": {"h1d": {"abs": 0, "ready": True}, "drawdown": {"in_drawdown": False, "depth": "none"}}},
        market_cycle={"available": True, "mode": "range", "headline": "BTC sideways"},
        asset_closes={"BTC": btc, "SOL": sol},
    )
    sol_row = next(r for r in plan["asset_signals"] if r["symbol"] == "SOL")
    assert sol_row["label"] == "accumulate"
    assert sol_row["label"] != "reduce"
    assert any("SOL relative strength" in c for c in plan["checklist"])


def test_bear_macro_negative_rs_most_conservative():
    """BTC bear + asset weaker than BTC → reduce (both signals risk-off)."""
    btc = _ramp(100, 85)   # −15%
    alt = _ramp(100, 70)   # −30% → RS ≈ −15%
    m = build_asset_momentum("LINK", alt, btc, cycle_mode="risk_off")
    assert m["macro_signal"] < 0
    assert m["rs_30d"] is not None and m["rs_30d"] < 0
    assert m["label"] == "reduce"
    assert m["asset_risk_score"] < -0.3


def test_bull_macro_lagging_asset_mixed_not_blind_ok():
    """BTC bull but asset lags → mixed / not blind accumulate."""
    btc = _ramp(100, 130)  # +30%
    alt = _ramp(100, 105)  # +5% → RS ≈ −25%
    m = build_asset_momentum("AAVE", alt, btc, cycle_mode="risk_on")
    assert m["macro_signal"] > 0
    assert m["rs_30d"] is not None and m["rs_30d"] < -0.15
    # Blended: positive macro 0.4*0.6=0.24, RS signal ~-1 * 0.6 = -0.6 → score ~-0.36 → reduce
    assert m["label"] in {"hold", "reduce"}
    assert m["label"] != "accumulate"
    assert "lagging" in m["explain"].lower() or m["label"] == "reduce"


def test_rs_does_not_override_drawdown_profit_lock_block():
    """Strong SOL RS must not force profit_lock while drawdown gate blocks."""
    btc = _ramp(100, 100)
    sol = _ramp(100, 140)
    hist = {
        "today_pnl": {"abs": 40.0, "pct": 0.01},
        "pnl_context": {
            "h1d": {"abs": 40.0, "pct": 0.01, "ready": True},
            "h7d": {"abs": -50.0, "pct": -0.01, "ready": True},
            "h30d": {"abs": -800.0, "pct": -0.12, "ready": True},
            "drawdown": {
                "dd_30_pct": -0.12,
                "dd_90_pct": -0.18,
                "bounce_from_30d_low_pct": 0.01,
                "in_drawdown": True,
                "depth": "significant",
            },
        },
    }
    plan = build_action_plan(
        {
            "available": True,
            "total_usdt": 5000,
            "stable_pct": 15,
            "holdings": [
                {"symbol": "SOL", "value_usdt": 500, "pct": 10},
                {"symbol": "LINK", "value_usdt": 200, "pct": 4},
            ],
        },
        hist,
        market_cycle={"available": True, "mode": "range", "headline": "neutral"},
        asset_closes={"BTC": btc, "SOL": sol},
    )
    assert plan["mode"] != "profit_lock"
    assert plan["pnl_context"]["lock_allowed"] is False
    # RS layer still present for explainability
    assert any(r["symbol"] == "SOL" and r["label"] == "accumulate" for r in plan["asset_signals"])
