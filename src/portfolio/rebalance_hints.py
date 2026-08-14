"""Target weights and threshold-based rebalance hints (suggestions only)."""

from __future__ import annotations

from typing import Dict, List, Tuple

# Same targets as srebalancing.py — suggestions only, never auto-trade from UI
TARGET_WEIGHTS: Dict[str, float] = {
    "BTC": 28.0,
    "ETH": 20.0,
    "SOL": 8.0,
    "BNB": 6.0,
    "XRP": 3.0,
    "LINK": 4.0,
    "AAVE": 4.0,
    "ZEC": 4.0,
    "FIL": 2.0,
    "PAXG": 6.0,
    "USDT": 15.0,
}

# Relative deviation from target (%) before suggesting action
REBALANCE_THRESHOLD_PCT: Dict[str, float] = {
    "BTC": 15,
    "ETH": 15,
    "BNB": 15,
    "USDT": 15,
    "SOL": 25,
    "XRP": 25,
    "LINK": 25,
    "AAVE": 25,
    "ZEC": 25,
    "FIL": 25,
    "PAXG": 20,
}

MIN_ACTION_AMOUNT_USDT = 20.0


def check_rebalance(
    current_weights: Dict[str, float],
    current_values_usdt: Dict[str, float],
    total_usdt: float,
) -> Tuple[List[dict], List[dict]]:
    """
    Returns (actionable_signals, minor_deviations).
    Actionable = past % threshold AND |amount_usdt| >= MIN_ACTION_AMOUNT_USDT.
    """
    signals: List[dict] = []
    minor: List[dict] = []

    if total_usdt <= 0:
        return signals, minor

    for asset, target_weight in TARGET_WEIGHTS.items():
        current_weight = float(current_weights.get(asset, 0.0))
        current_value = float(current_values_usdt.get(asset, 0.0))
        if target_weight <= 0:
            continue
        deviation_pct = (current_weight - target_weight) / target_weight * 100.0
        threshold = REBALANCE_THRESHOLD_PCT.get(asset, 20)

        if abs(deviation_pct) <= threshold:
            continue

        target_value = total_usdt * (target_weight / 100.0)
        amount_usdt = target_value - current_value
        action = "BUY" if current_weight < target_weight else "SELL"

        entry = {
            "asset": asset,
            "current_pct": round(current_weight, 2),
            "target_pct": target_weight,
            "deviation_pct": round(deviation_pct, 2),
            "action": action,
            "amount_usdt": round(amount_usdt, 2),
            "threshold_pct": threshold,
        }

        if abs(amount_usdt) < MIN_ACTION_AMOUNT_USDT:
            entry["action"] = "HOLD"
            entry["below_min_threshold"] = True
            entry["note"] = f"Drift past {threshold}% but under ${MIN_ACTION_AMOUNT_USDT:.0f} — skip fees"
            minor.append(entry)
        else:
            entry["below_min_threshold"] = False
            entry["note"] = (
                f"{action} ~${abs(amount_usdt):.0f} to reach {target_weight:.0f}% "
                f"(drift {deviation_pct:+.0f}% vs ±{threshold}% band)"
            )
            signals.append(entry)

    signals.sort(key=lambda x: abs(x["amount_usdt"]), reverse=True)
    return signals, minor


def rebalance_from_portfolio(portfolio: dict) -> dict:
    """Build rebalance view from fetch_portfolio_snapshot payload."""
    total = float(portfolio.get("total_usdt") or 0.0)
    assets = portfolio.get("assets") or {}
    current_weights = {
        sym: float(info.get("pct") or 0.0) for sym, info in assets.items()
    }
    current_values = {
        sym: float(info.get("value_usdt") or 0.0) for sym, info in assets.items()
    }
    # Include zero weight for missing target assets
    for sym in TARGET_WEIGHTS:
        current_weights.setdefault(sym, 0.0)
        current_values.setdefault(sym, 0.0)

    signals, minor = check_rebalance(current_weights, current_values, total)

    allocation = []
    for sym, target in TARGET_WEIGHTS.items():
        cur = current_weights.get(sym, 0.0)
        allocation.append({
            "asset": sym,
            "current_pct": round(cur, 2),
            "target_pct": target,
            "gap_pct": round(cur - target, 2),
            "value_usdt": round(current_values.get(sym, 0.0), 2),
        })

    return {
        "policy": (
            "Threshold rebalance only — not daily. "
            f"Act when relative drift exceeds asset band and size ≥ ${MIN_ACTION_AMOUNT_USDT:.0f}."
        ),
        "min_action_usdt": MIN_ACTION_AMOUNT_USDT,
        "targets": TARGET_WEIGHTS,
        "thresholds_pct": REBALANCE_THRESHOLD_PCT,
        "actionable": signals,
        "minor": minor,
        "allocation": allocation,
        "needs_rebalance": len(signals) > 0,
    }
