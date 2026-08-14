"""BTC/Alt season phase from dominance + alt index (allocation targets only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.config import CycleRebalanceConfig
from src.portfolio.season_data import SeasonDataStore


PHASES = ("btc_season", "neutral", "alt_season")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def classify_btc_d_trend(
    history: List[dict],
    *,
    lookback_days: int = 30,
    flat_band_pct: float = 0.3,
    now: Optional[datetime] = None,
) -> str:
    """rising | falling | flat from BTC.D snapshots."""
    now = now or _utcnow()
    if not history:
        return "flat"
    cutoff = (now.date() - timedelta(days=lookback_days)).isoformat()
    window = [h for h in history if (h.get("date") or "") <= now.date().isoformat()]
    window = [h for h in window if (h.get("date") or "") >= cutoff]
    if len(window) < 2:
        # fall back to full history ends if lookback empty
        window = list(history)
    if len(window) < 2:
        return "flat"
    first = float(window[0].get("btc_dominance") or 0)
    last = float(window[-1].get("btc_dominance") or 0)
    delta = last - first
    if abs(delta) < flat_band_pct:
        return "flat"
    return "rising" if delta > 0 else "falling"


def classify_phase(
    *,
    btc_d_trend: str,
    alt_season_index: Optional[float],
    alt_index_btc_max: float = 25.0,
    alt_index_alt_min: float = 75.0,
) -> str:
    """
    BTC Season: BTC.D rising AND index < btc_max
    Alt Season: BTC.D falling AND index > alt_min
    else Neutral (incl. conflicting signals / missing index)
    """
    if alt_season_index is None:
        return "neutral"
    idx = float(alt_season_index)
    if btc_d_trend == "rising" and idx < alt_index_btc_max:
        return "btc_season"
    if btc_d_trend == "falling" and idx > alt_index_alt_min:
        return "alt_season"
    return "neutral"


def phase_targets(cfg: CycleRebalanceConfig, phase: str) -> Dict[str, float]:
    phases = cfg.phases or {}
    targets = dict(phases.get(phase) or phases.get("neutral") or {})
    if not targets and phases.get("neutral"):
        targets = dict(phases["neutral"])
    return {k.upper(): float(v) for k, v in targets.items()}


def _load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def assess_market_season(
    cfg: Optional[CycleRebalanceConfig] = None,
    *,
    output_dir: Union[str, Path] = "out",
    fetch: bool = True,
    store: Optional[SeasonDataStore] = None,
    snapshot: Optional[dict] = None,
    history: Optional[List[dict]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Season layer for rebalance targets (not price-structure cycle).

    Returns phase, metrics, targets, phase_changed warning fields.
    """
    cfg = cfg or CycleRebalanceConfig()
    out = Path(output_dir)
    now = now or _utcnow()
    state_path = out / "season_state.json"

    if not cfg.enabled:
        targets = phase_targets(cfg, "neutral")
        return {
            "available": True,
            "enabled": False,
            "phase": "neutral",
            "btc_dominance": None,
            "btc_d_trend": "flat",
            "alt_season_index": None,
            "targets": targets,
            "phase_changed": False,
            "previous_phase": None,
            "headline": "Cycle rebalance disabled — using neutral targets.",
            "checklist": [],
            "note": "",
        }

    data = store or SeasonDataStore(out, cache_ttl_hours=cfg.cache_ttl_hours)
    try:
        snap = snapshot if snapshot is not None else data.get_snapshot(fetch=fetch)
    except Exception as exc:  # noqa: BLE001
        targets = phase_targets(cfg, "neutral")
        return {
            "available": False,
            "enabled": True,
            "phase": "neutral",
            "btc_dominance": None,
            "btc_d_trend": "flat",
            "alt_season_index": None,
            "targets": targets,
            "phase_changed": False,
            "previous_phase": None,
            "headline": "Could not read season data (CoinGecko).",
            "error": str(exc),
            "checklist": ["Using neutral targets until season data is available."],
            "note": "",
        }

    if not snap:
        targets = phase_targets(cfg, "neutral")
        return {
            "available": False,
            "enabled": True,
            "phase": "neutral",
            "btc_dominance": None,
            "btc_d_trend": "flat",
            "alt_season_index": None,
            "targets": targets,
            "phase_changed": False,
            "previous_phase": None,
            "headline": "No season snapshot yet.",
            "checklist": ["Sync later or wait for CoinGecko cache."],
            "note": "",
        }

    hist = history if history is not None else data.btc_d_history()
    trend = classify_btc_d_trend(
        hist,
        lookback_days=cfg.btc_d_lookback_days,
        flat_band_pct=cfg.btc_d_flat_band_pct,
        now=now,
    )
    index = snap.get("alt_season_index")
    phase = classify_phase(
        btc_d_trend=trend,
        alt_season_index=index,
        alt_index_btc_max=cfg.alt_index_btc_max,
        alt_index_alt_min=cfg.alt_index_alt_min,
    )
    targets = phase_targets(cfg, phase)

    prev_state = _load_state(state_path)
    previous_phase = prev_state.get("phase")
    phase_changed = bool(previous_phase and previous_phase != phase)
    _save_state(state_path, {
        "phase": phase,
        "previous_phase": previous_phase if phase_changed else prev_state.get("previous_phase"),
        "changed_at": now.isoformat(timespec="seconds") if phase_changed else prev_state.get("changed_at"),
        "updated_at": now.isoformat(timespec="seconds"),
        "btc_dominance": snap.get("btc_dominance"),
        "alt_season_index": index,
        "btc_d_trend": trend,
    })

    btc_d = snap.get("btc_dominance")
    labels = {
        "btc_season": "BTC season",
        "neutral": "Neutral season",
        "alt_season": "Alt season",
    }
    headline = (
        f"{labels.get(phase, phase)}: BTC.D {btc_d}% ({trend}), "
        f"alt-index {index if index is not None else '—'} "
        f"(btc<{cfg.alt_index_btc_max} / alt>{cfg.alt_index_alt_min})."
    )
    checklist = [
        "Season sets rebalance targets only — not a buy/sell-all signal.",
        f"Phase targets active: {phase}.",
        f"Satellites {', '.join(cfg.no_refill)}: never buy back (no refill).",
    ]
    if phase_changed:
        checklist.insert(
            0,
            f"Phase just changed ({previous_phase} → {phase}). "
            "Do not rebalance on the first tick — confirm over a day or two.",
        )
    if trend == "flat":
        checklist.append(
            "BTC.D trend is flat or history is short — season stays neutral unless "
            "both dominance trend and alt-index agree."
        )

    return {
        "available": True,
        "enabled": True,
        "phase": phase,
        "btc_dominance": btc_d,
        "btc_d_trend": trend,
        "alt_season_index": index,
        "alts_compared": snap.get("alts_compared"),
        "btc_return_90d": snap.get("btc_return_90d"),
        "targets": targets,
        "phase_changed": phase_changed,
        "previous_phase": previous_phase if phase_changed else None,
        "fetched_at": snap.get("fetched_at"),
        "headline": headline,
        "checklist": checklist,
        "note": (
            "Alt-index proxy = % of top alts whose 90d return beat BTC (CoinGecko). "
            "Price-structure cycle (risk_off/…) is a separate card."
        ),
        "sample": snap.get("sample") or [],
    }
