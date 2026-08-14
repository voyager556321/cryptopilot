"""BTC-centric market cycle / liquidity regime (advice layer, not a crystal ball)."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _binance_daily_btc(limit: int = 120) -> List[dict]:
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol=BTCUSDT&interval=1d&limit={limit}"
    )
    with urllib.request.urlopen(url, timeout=12) as resp:
        raw = json.loads(resp.read())
    out = []
    for row in raw:
        out.append({
            "ts": int(row[0]),
            "date": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date().isoformat(),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        })
    return out


def assess_market_cycle(
    *,
    bars: Optional[List[dict]] = None,
    stable_pct: Optional[float] = None,
    fetch: bool = True,
) -> Dict[str, Any]:
    """
    Classify a coarse regime for UI advice.

    Modes:
      - risk_off: deep drawdown / weak structure — prioritize cash, no chase
      - bounce_watch: rebound inside larger drawdown — treat as relief, not new bull
      - range: sideways — grid / patience / rebalance
      - risk_on: recovering toward highs — still trim strength, don't FOMO alts
    """
    try:
        bars = bars if bars is not None else (_binance_daily_btc() if fetch else [])
    except Exception as exc:  # noqa: BLE001 — network/public API
        return {
            "available": False,
            "mode": "unknown",
            "headline": "Could not read BTC cycle (network).",
            "error": str(exc),
            "checklist": [],
            "levels": {},
        }

    if len(bars) < 30:
        return {
            "available": False,
            "mode": "unknown",
            "headline": "Not enough data to assess the cycle.",
            "checklist": [],
            "levels": {},
        }

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    px = closes[-1]
    high_90 = max(highs[-90:]) if len(highs) >= 90 else max(highs)
    high_30 = max(highs[-30:])
    low_45 = min(lows[-45:]) if len(lows) >= 45 else min(lows)
    ret_30 = (px / closes[-31] - 1.0) if len(closes) >= 31 else None
    ret_7 = (px / closes[-8] - 1.0) if len(closes) >= 8 else None
    dd_90 = px / high_90 - 1.0
    bounce_from_low = px / low_45 - 1.0

    # Coarse structure
    if dd_90 <= -0.28:
        mode = "risk_off"
        headline = (
            f"Risk-off structure: BTC ${px:,.0f}, −{abs(dd_90)*100:.0f}% from 90d high "
            f"(${high_90:,.0f}). Priority — cushion, not chase."
        )
    elif dd_90 <= -0.12 and bounce_from_low >= 0.06 and (ret_7 or 0) > 0:
        mode = "bounce_watch"
        headline = (
            f"Bounce inside a drawdown: BTC ${px:,.0f} "
            f"(+{bounce_from_low*100:.0f}% from local low ${low_45:,.0f}, "
            f"but still {dd_90*100:.0f}% from 90d high). Relief by default, not a new bull."
        )
    elif abs(dd_90) < 0.12 and ret_30 is not None and abs(ret_30) < 0.08:
        mode = "range"
        headline = (
            f"Sideways / range: BTC ${px:,.0f}, near 90d high ${high_90:,.0f}. "
            f"Grid + rebalance, no FOMO."
        )
    elif dd_90 > -0.12 and (ret_30 or 0) > 0:
        mode = "risk_on"
        headline = (
            f"Soft risk-on: BTC ${px:,.0f} holding above the deep pit. "
            f"Keep core, but trim alts; don't dump all USDT."
        )
    else:
        mode = "range"
        headline = f"Neutral / mixed: BTC ${px:,.0f}. No extremes."

    # Suggested limit buys (core only) — percentages off spot, not promises
    levels = {
        "spot": round(px, 2),
        "high_90d": round(high_90, 2),
        "high_30d": round(high_30, 2),
        "low_45d": round(low_45, 2),
        "drawdown_90d_pct": round(dd_90 * 100, 2),
        "bounce_from_45d_low_pct": round(bounce_from_low * 100, 2),
        "return_7d_pct": None if ret_7 is None else round(ret_7 * 100, 2),
        "return_30d_pct": None if ret_30 is None else round(ret_30 * 100, 2),
        "limit_buy_btc": [
            {"label": "mild dip", "price": round(px * 0.92, 0)},
            {"label": "deeper", "price": round(px * 0.85, 0)},
            {"label": "washout zone", "price": round(min(px * 0.78, low_45 * 0.95), 0)},
        ],
    }

    stable = stable_pct
    checklist: List[str] = []
    if mode == "risk_off":
        checklist = [
            "Don't buy alts just because they're 'cheap'",
            "USDT target ≥25% while structure is weak",
            "Hold core; trim only overweight / defense days",
            "BTC limits below spot — OK; market FOMO — no",
        ]
    elif mode == "bounce_watch":
        checklist = [
            "Don't treat the bounce as a new bull start",
            "Profit-lock on green days matters more than adds",
            "Build USDT from income / trims into Aug–Sep",
            "Deeper limits — yes; chase now — no",
            "Full cash-out is unnecessary (markets can spike locally)",
        ]
    elif mode == "range":
        checklist = [
            "Spot grid / patience beats active trading",
            "Rebalance by weights, not by today's headlines",
            "USDT ~20%+",
        ]
    else:  # risk_on
        checklist = [
            "Keep BTC/ETH core",
            "Trim alts when weights drift",
            "Don't dump the whole cushion into FOMO",
        ]

    if stable is not None:
        if mode in {"risk_off", "bounce_watch"} and stable < 20:
            checklist.insert(0, f"USDT now {stable:.1f}% — raise the cushion with trims")
        elif stable >= 20:
            checklist.append(f"Cushion {stable:.1f}% — OK for later limit adds to core")

    return {
        "available": True,
        "mode": mode,
        "headline": headline,
        "checklist": checklist,
        "levels": levels,
        "note": (
            "Cycle = coarse BTC structure mode + your rules. "
            "Not a September bottom call and not an all-in/all-out signal."
        ),
        "macro_context": (
            "Rates/ETF/liquidity can keep Aug–Sep dump risk alive even during "
            "local rallies. A bounce ≠ a new global bull until durable inflows "
            "and easier money conditions show up."
        ),
    }
