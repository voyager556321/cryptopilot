"""Recommendation journal + forward outcome windows."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def attach_forward_returns(
    journal: Sequence[Dict[str, Any]],
    equity_by_date: Dict[str, float],
    dates: Sequence[str],
) -> List[Dict[str, Any]]:
    """Attach what happened 1d / 3d / 7d later using equity map (sim or historical)."""
    idx = {d: i for i, d in enumerate(dates)}
    out: List[Dict[str, Any]] = []
    for row in journal:
        r = dict(row)
        d = str(r.get("date") or "")
        i = idx.get(d)
        base = equity_by_date.get(d)
        fwd: Dict[str, Any] = {}
        if i is not None and base and base > 0:
            for horizon, key in ((1, "ret_1d"), (3, "ret_3d"), (7, "ret_7d")):
                j = i + horizon
                if j < len(dates):
                    nxt = equity_by_date.get(dates[j])
                    if nxt is not None:
                        fwd[key] = round(nxt / base - 1.0, 6)
                        fwd[f"equity_{key}"] = round(float(nxt), 2)
                    else:
                        fwd[key] = None
                else:
                    fwd[key] = None
        else:
            fwd = {"ret_1d": None, "ret_3d": None, "ret_7d": None}
        r["forward"] = fwd
        out.append(r)
    return out


def summarize_action_forwards(journal: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """E.g. share of PROFIT_LOCK days where market was down over next 3d."""
    by_action: Dict[str, Dict[str, Any]] = {}
    for row in journal:
        action = str(row.get("action") or "UNKNOWN").upper()
        bucket = by_action.setdefault(
            action,
            {"count": 0, "down_1d": 0, "down_3d": 0, "down_7d": 0, "n_1d": 0, "n_3d": 0, "n_7d": 0},
        )
        bucket["count"] += 1
        fwd = row.get("forward") or {}
        for h, nkey, dkey in (
            ("ret_1d", "n_1d", "down_1d"),
            ("ret_3d", "n_3d", "down_3d"),
            ("ret_7d", "n_7d", "down_7d"),
        ):
            v = fwd.get(h)
            if v is None:
                continue
            bucket[nkey] += 1
            if float(v) < 0:
                bucket[dkey] += 1

    summary: Dict[str, Any] = {}
    for action, b in by_action.items():
        summary[action] = {
            "count": b["count"],
            "pct_down_1d": round(b["down_1d"] / b["n_1d"], 4) if b["n_1d"] else None,
            "pct_down_3d": round(b["down_3d"] / b["n_3d"], 4) if b["n_3d"] else None,
            "pct_down_7d": round(b["down_7d"] / b["n_7d"], 4) if b["n_7d"] else None,
            "samples_1d": b["n_1d"],
            "samples_3d": b["n_3d"],
            "samples_7d": b["n_7d"],
        }
    return summary
