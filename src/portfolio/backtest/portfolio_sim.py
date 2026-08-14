"""Sleeve portfolio helpers for backtest (reconstruct bags from history %)."""

from __future__ import annotations

from typing import Any, Dict, List


def portfolio_from_sleeves(
    *,
    total_usdt: float,
    btc_eth_pct: float,
    stable_pct: float,
    alts_pct: float,
) -> Dict[str, Any]:
    """Synthetic holdings so production ``build_action_plan`` can allocate trims."""
    total = max(0.0, float(total_usdt))
    be = total * float(btc_eth_pct) / 100.0
    st = total * float(stable_pct) / 100.0
    al = total * float(alts_pct) / 100.0
    # Normalize residual rounding into USDT
    residual = total - (be + st + al)
    st = max(0.0, st + residual)

    holdings: List[dict] = [
        {"symbol": "BTC", "value_usdt": round(be * 0.70, 4), "asset_class": "crypto"},
        {"symbol": "ETH", "value_usdt": round(be * 0.30, 4), "asset_class": "crypto"},
        {"symbol": "USDT", "value_usdt": round(st, 4), "asset_class": "stable"},
        {"symbol": "SOL", "value_usdt": round(al * 0.40, 4), "asset_class": "crypto"},
        {"symbol": "LINK", "value_usdt": round(al * 0.30, 4), "asset_class": "crypto"},
        {"symbol": "AAVE", "value_usdt": round(al * 0.30, 4), "asset_class": "crypto"},
    ]
    for h in holdings:
        h["pct"] = round(h["value_usdt"] / total * 100, 4) if total else 0.0

    return {
        "available": True,
        "total_usdt": round(total, 4),
        "btc_eth_pct": round(float(btc_eth_pct), 4),
        "stable_pct": round(st / total * 100, 4) if total else 0.0,
        "alts_pct": round(al / total * 100, 4) if total else 0.0,
        "holdings": holdings,
    }


def sleeves_from_state(btc_eth: float, alts: float, usdt: float) -> Dict[str, float]:
    total = max(0.0, btc_eth + alts + usdt)
    if total <= 0:
        return {"total_usdt": 0.0, "btc_eth_pct": 0.0, "stable_pct": 100.0, "alts_pct": 0.0}
    return {
        "total_usdt": total,
        "btc_eth_pct": btc_eth / total * 100,
        "stable_pct": usdt / total * 100,
        "alts_pct": alts / total * 100,
    }


def apply_lock(btc_eth: float, alts: float, usdt: float, lock_usdt: float) -> tuple[float, float, float, float]:
    """Move ``lock_usdt`` from alts first, then btc_eth, into USDT. Returns new sleeves + filled."""
    need = max(0.0, float(lock_usdt))
    filled = 0.0
    if need <= 0:
        return btc_eth, alts, usdt, 0.0
    take_alts = min(alts, need)
    alts -= take_alts
    need -= take_alts
    filled += take_alts
    if need > 0:
        take_be = min(btc_eth, need)
        btc_eth -= take_be
        need -= take_be
        filled += take_be
    usdt += filled
    return btc_eth, alts, usdt, filled


def apply_risk_return(btc_eth: float, alts: float, usdt: float, r_btc: float, *, alt_beta: float = 1.25) -> tuple[float, float, float]:
    """USDT flat; BTC/ETH sleeve follows BTC; alts follow BTC * alt_beta (clipped)."""
    r_alt = max(-0.95, min(0.95, float(r_btc) * float(alt_beta)))
    return btc_eth * (1.0 + float(r_btc)), alts * (1.0 + r_alt), usdt
