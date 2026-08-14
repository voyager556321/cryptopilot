"""Target weights and threshold-based rebalance hints (suggestions only)."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple

# Fallback = neutral full-book targets (also cycle_rebalance.phases.neutral)
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

# Satellite bags: trim when heavy, never "buy back to target" (no averaging).
NO_REFILL: set = {"AAVE", "LINK", "FIL", "XRP"}


def check_rebalance(
    current_weights: Dict[str, float],
    current_values_usdt: Dict[str, float],
    total_usdt: float,
    *,
    targets: Optional[Dict[str, float]] = None,
    thresholds_pct: Optional[Dict[str, float]] = None,
    no_refill: Optional[Sequence[str]] = None,
    min_action_usdt: float = MIN_ACTION_AMOUNT_USDT,
) -> Tuple[List[dict], List[dict]]:
    """
    Returns (actionable_signals, minor_deviations).
    Actionable = past % threshold AND |amount_usdt| >= min_action_usdt.
    Underweight satellites in no_refill never become BUY.
    """
    target_map = {k.upper(): float(v) for k, v in (targets or TARGET_WEIGHTS).items()}
    thr_map = {k.upper(): float(v) for k, v in (thresholds_pct or REBALANCE_THRESHOLD_PCT).items()}
    blocked: Set[str] = {s.upper() for s in (no_refill if no_refill is not None else NO_REFILL)}

    signals: List[dict] = []
    minor: List[dict] = []

    if total_usdt <= 0:
        return signals, minor

    for asset, target_weight in target_map.items():
        current_weight = float(current_weights.get(asset, 0.0))
        current_value = float(current_values_usdt.get(asset, 0.0))
        if target_weight <= 0:
            continue
        deviation_pct = (current_weight - target_weight) / target_weight * 100.0
        threshold = thr_map.get(asset, 20)

        if abs(deviation_pct) <= threshold:
            continue

        target_value = total_usdt * (target_weight / 100.0)
        amount_usdt = target_value - current_value
        action = "BUY" if current_weight < target_weight else "SELL"

        if action == "BUY" and asset in blocked:
            entry = {
                "asset": asset,
                "current_pct": round(current_weight, 2),
                "target_pct": target_weight,
                "deviation_pct": round(deviation_pct, 2),
                "action": "HOLD",
                "amount_usdt": round(amount_usdt, 2),
                "threshold_pct": threshold,
                "below_min_threshold": False,
                "note": (
                    f"Under {target_weight:.0f}% after a trim — do not buy back. "
                    f"Satellite (no refill). Gap ~${abs(amount_usdt):.0f} stays cash/USDT."
                ),
            }
            minor.append(entry)
            continue

        entry = {
            "asset": asset,
            "current_pct": round(current_weight, 2),
            "target_pct": target_weight,
            "deviation_pct": round(deviation_pct, 2),
            "action": action,
            "amount_usdt": round(amount_usdt, 2),
            "threshold_pct": threshold,
        }

        if abs(amount_usdt) < min_action_usdt:
            entry["action"] = "HOLD"
            entry["below_min_threshold"] = True
            entry["note"] = f"Drift past {threshold}% but under ${min_action_usdt:.0f} — skip fees"
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


def rebalance_from_portfolio(
    portfolio: dict,
    *,
    targets: Optional[Dict[str, float]] = None,
    thresholds_pct: Optional[Dict[str, float]] = None,
    no_refill: Optional[Sequence[str]] = None,
    min_action_usdt: float = MIN_ACTION_AMOUNT_USDT,
    season: Optional[dict] = None,
) -> dict:
    """Build rebalance view from fetch_portfolio_snapshot payload."""
    total = float(portfolio.get("total_usdt") or 0.0)
    assets = portfolio.get("assets") or {}
    current_weights = {
        sym: float(info.get("pct") or 0.0) for sym, info in assets.items()
    }
    current_values = {
        sym: float(info.get("value_usdt") or 0.0) for sym, info in assets.items()
    }
    target_map = {k.upper(): float(v) for k, v in (targets or TARGET_WEIGHTS).items()}
    thr_map = thresholds_pct or REBALANCE_THRESHOLD_PCT
    blocked = list(no_refill if no_refill is not None else sorted(NO_REFILL))

    for sym in target_map:
        current_weights.setdefault(sym, 0.0)
        current_values.setdefault(sym, 0.0)

    signals, minor = check_rebalance(
        current_weights,
        current_values,
        total,
        targets=target_map,
        thresholds_pct=thr_map,
        no_refill=blocked,
        min_action_usdt=min_action_usdt,
    )

    allocation = []
    for sym, target in target_map.items():
        cur = current_weights.get(sym, 0.0)
        allocation.append({
            "asset": sym,
            "current_pct": round(cur, 2),
            "target_pct": target,
            "gap_pct": round(cur - target, 2),
            "value_usdt": round(current_values.get(sym, 0.0), 2),
        })

    phase = (season or {}).get("phase") or "neutral"
    phase_changed = bool((season or {}).get("phase_changed"))
    policy = (
        f"Cycle-aware threshold rebalance · phase={phase}. "
        f"Relative drift bands; size ≥ ${min_action_usdt:.0f}. "
        f"Satellites {', '.join(sorted(blocked))}: sell if heavy, never buy back."
    )
    if phase_changed:
        prev = (season or {}).get("previous_phase")
        policy = (
            f"PHASE CHANGED ({prev} → {phase}) — confirm before acting. "
        ) + policy

    return {
        "policy": policy,
        "min_action_usdt": min_action_usdt,
        "targets": target_map,
        "thresholds_pct": {k.upper(): float(v) for k, v in thr_map.items()},
        "no_refill": sorted(blocked),
        "phase": phase,
        "phase_changed": phase_changed,
        "season": {
            "phase": phase,
            "btc_dominance": (season or {}).get("btc_dominance"),
            "btc_d_trend": (season or {}).get("btc_d_trend"),
            "alt_season_index": (season or {}).get("alt_season_index"),
            "phase_changed": phase_changed,
            "previous_phase": (season or {}).get("previous_phase"),
            "headline": (season or {}).get("headline"),
        } if season else None,
        "actionable": signals,
        "minor": minor,
        "allocation": allocation,
        "needs_rebalance": len(signals) > 0,
    }
