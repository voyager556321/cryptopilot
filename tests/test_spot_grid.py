"""Tests for paper spot grid."""

from src.strategy.spot_grid import SpotGridPaper


def test_grid_builds_and_fills_roundtrip(tmp_path):
    grid = SpotGridPaper(
        tmp_path,
        symbol="BTC",
        levels=6,
        range_pct=0.06,
        order_size_usdt=100,
        fee_bps=10,
        bank_usdt=2000,
    )
    mid = 100.0
    grid.ensure_grid(mid)
    s = grid.summary(price=mid)
    assert s["status"] == "active"
    assert len(s["levels"]) == 6
    assert s["low"] < mid < s["high"]

    buy_lvl = min(l["price"] for l in s["levels"] if l["side"] == "buy")
    step = float(s["step"])

    # Bootstrap last_price above the buy level, then cross down
    grid._state["last_price"] = mid
    fills = grid.on_price(buy_lvl - 0.01)
    assert any(f["side"] == "buy" for f in fills)
    assert grid.summary()["inventory"] > 0

    # Cross up through the flipped sell level
    grid._state["last_price"] = buy_lvl - 0.01
    sells = grid.on_price(buy_lvl + step + 0.01)
    assert any(f["side"] == "sell" for f in sells)
    summary = grid.summary(price=buy_lvl + step + 0.01)
    assert summary["fill_count"] >= 2
    assert summary["realized_pnl_usdt"] != 0 or summary["fees_paid"] > 0


def test_grid_reset(tmp_path):
    grid = SpotGridPaper(tmp_path, bank_usdt=500)
    grid.ensure_grid(50)
    grid.reset(bank_usdt=500)
    assert grid.summary()["status"] == "idle"
    assert grid.summary()["cash_usdt"] == 500
