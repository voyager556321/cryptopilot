"""Unit tests for BTC/Alt season phase logic (no network)."""

from datetime import datetime, timezone

from src.config import CycleRebalanceConfig
from src.portfolio.season import (
    assess_market_season,
    classify_btc_d_trend,
    classify_phase,
    phase_targets,
)
from src.portfolio.rebalance_hints import check_rebalance, rebalance_from_portfolio


def test_classify_phase_btc_season():
    assert classify_phase(btc_d_trend="rising", alt_season_index=20) == "btc_season"


def test_classify_phase_alt_season():
    assert classify_phase(btc_d_trend="falling", alt_season_index=80) == "alt_season"


def test_classify_phase_neutral_on_conflict():
    assert classify_phase(btc_d_trend="rising", alt_season_index=80) == "neutral"
    assert classify_phase(btc_d_trend="falling", alt_season_index=20) == "neutral"
    assert classify_phase(btc_d_trend="flat", alt_season_index=90) == "neutral"
    assert classify_phase(btc_d_trend="rising", alt_season_index=None) == "neutral"


def test_btc_d_trend_rising_falling_flat():
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    rising = [
        {"date": "2026-07-15", "btc_dominance": 50.0},
        {"date": "2026-08-14", "btc_dominance": 55.0},
    ]
    falling = [
        {"date": "2026-07-15", "btc_dominance": 55.0},
        {"date": "2026-08-14", "btc_dominance": 50.0},
    ]
    flat = [
        {"date": "2026-07-15", "btc_dominance": 52.0},
        {"date": "2026-08-14", "btc_dominance": 52.1},
    ]
    assert classify_btc_d_trend(rising, now=now) == "rising"
    assert classify_btc_d_trend(falling, now=now) == "falling"
    assert classify_btc_d_trend(flat, now=now) == "flat"


def test_phase_targets_from_config():
    cfg = CycleRebalanceConfig()
    btc = phase_targets(cfg, "btc_season")
    assert btc["BTC"] == 35
    assert abs(sum(btc.values()) - 100) < 0.01


def test_assess_market_season_phase_changed(tmp_path):
    cfg = CycleRebalanceConfig()
    snap = {
        "fetched_at": "2026-08-14T12:00:00+00:00",
        "btc_dominance": 55.0,
        "alt_season_index": 15.0,
        "alts_compared": 40,
    }
    hist = [
        {"date": "2026-07-15", "btc_dominance": 50.0},
        {"date": "2026-08-14", "btc_dominance": 55.0},
    ]
    # seed previous phase
    (tmp_path / "season_state.json").write_text(
        '{"phase": "neutral", "updated_at": "2026-08-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    first = assess_market_season(
        cfg,
        output_dir=tmp_path,
        fetch=False,
        snapshot=snap,
        history=hist,
        now=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    assert first["phase"] == "btc_season"
    assert first["phase_changed"] is True
    assert first["previous_phase"] == "neutral"
    assert first["targets"]["BTC"] == 35

    second = assess_market_season(
        cfg,
        output_dir=tmp_path,
        fetch=False,
        snapshot=snap,
        history=hist,
        now=datetime(2026, 8, 14, 1, tzinfo=timezone.utc),
    )
    assert second["phase"] == "btc_season"
    assert second["phase_changed"] is False


def test_rebalance_uses_phase_targets():
    portfolio = {
        "available": True,
        "total_usdt": 10000,
        "assets": {
            "BTC": {"pct": 22.0, "value_usdt": 2200},
            "ETH": {"pct": 18.0, "value_usdt": 1800},
            "USDT": {"pct": 20.0, "value_usdt": 2000},
        },
    }
    season = {
        "phase": "btc_season",
        "phase_changed": False,
        "btc_dominance": 55,
        "btc_d_trend": "rising",
        "alt_season_index": 15,
        "headline": "BTC season",
    }
    targets = phase_targets(CycleRebalanceConfig(), "btc_season")
    view = rebalance_from_portfolio(portfolio, targets=targets, season=season)
    assert view["phase"] == "btc_season"
    assert view["targets"]["BTC"] == 35
    # BTC underweight vs 35% with large $ gap → BUY actionable likely
    assert any(s["asset"] == "BTC" and s["action"] == "BUY" for s in view["actionable"])


def test_rebalance_no_refill_still_blocks_aave_in_alt_season():
    weights = {k: 5.0 for k in [
        "BTC", "ETH", "SOL", "BNB", "XRP", "LINK", "ZEC", "FIL", "PAXG", "USDT",
    ]}
    weights["AAVE"] = 1.0  # under alt_season 5%
    weights["BTC"] = 20.0
    total = 100.0  # normalize later
    # rebuild to sum 100
    s = sum(weights.values())
    weights = {k: v / s * 100 for k, v in weights.items()}
    total_usdt = 5000.0
    values = {k: total_usdt * (v / 100) for k, v in weights.items()}
    targets = phase_targets(CycleRebalanceConfig(), "alt_season")
    signals, minor = check_rebalance(
        weights, values, total_usdt, targets=targets, no_refill=["AAVE", "LINK", "FIL", "XRP"]
    )
    assert not any(s["asset"] == "AAVE" and s["action"] == "BUY" for s in signals)
    assert any(m["asset"] == "AAVE" and m["action"] == "HOLD" for m in minor)
