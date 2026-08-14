"""Asset-level momentum via relative strength vs BTC (independent of macro cycle)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple


# Weighted blend: slightly favor RS so strong alts are not silenced by BTC range/bear
W_MACRO = 0.40
W_RS = 0.60

# RS of +20% over the window maps to RS signal ≈ +1.0 (clipped)
RS_SCALE = 0.20

# Windows (trading days ≈ calendar days for daily bars)
RS_WINDOW_7D = 7
RS_WINDOW_30D = 30


def rolling_return(closes: Sequence[float], days: int) -> Optional[float]:
    """
    Simple return over ``days`` bars: close[-1] / close[-(days+1)] - 1.
    Needs at least days+1 closes.
    """
    if days < 1 or closes is None:
        return None
    need = days + 1
    if len(closes) < need:
        return None
    start = float(closes[-(need)])
    end = float(closes[-1])
    if start <= 0:
        return None
    return end / start - 1.0


def relative_strength(
    asset_closes: Sequence[float],
    btc_closes: Sequence[float],
    days: int,
) -> Optional[float]:
    """RS = asset_return(days) - btc_return(days). Positive ⇒ asset beat BTC."""
    a = rolling_return(asset_closes, days)
    b = rolling_return(btc_closes, days)
    if a is None or b is None:
        return None
    return a - b


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def macro_to_signal(cycle_mode: str) -> float:
    """Map portfolio-level BTC cycle mode → continuous macro signal in [-1, 1]."""
    m = (cycle_mode or "unknown").lower()
    if m in {"risk_off", "bear"}:
        return -1.0
    if m in {"bounce_watch"}:
        return -0.35
    if m in {"range", "neutral", "unknown"}:
        return 0.0
    if m in {"risk_on", "bull"}:
        return 0.60
    return 0.0


def rs_to_signal(rs: Optional[float], *, scale: float = RS_SCALE) -> float:
    if rs is None or scale <= 0:
        return 0.0
    return _clip(rs / scale)


def score_label(score: float) -> str:
    if score >= 0.25:
        return "accumulate"
    if score >= -0.15:
        return "hold"
    return "reduce"


def build_asset_momentum(
    symbol: str,
    asset_closes: Sequence[float],
    btc_closes: Sequence[float],
    *,
    cycle_mode: str = "unknown",
    w_macro: float = W_MACRO,
    w_rs: float = W_RS,
    rs_scale: float = RS_SCALE,
) -> Dict[str, Any]:
    """
    AssetMomentum: rolling returns, RS vs BTC, and blended asset_risk_score.

    Portfolio profit-lock / drawdown gates are NOT decided here — this is an
    extra per-asset layer for hold / accumulate / reduce advice.
    """
    sym = (symbol or "").upper()
    ret_7 = rolling_return(asset_closes, RS_WINDOW_7D)
    ret_30 = rolling_return(asset_closes, RS_WINDOW_30D)
    btc_7 = rolling_return(btc_closes, RS_WINDOW_7D)
    btc_30 = rolling_return(btc_closes, RS_WINDOW_30D)
    rs_7 = relative_strength(asset_closes, btc_closes, RS_WINDOW_7D)
    rs_30 = relative_strength(asset_closes, btc_closes, RS_WINDOW_30D)

    # Prefer 30d RS for scoring; fall back to 7d
    rs_primary = rs_30 if rs_30 is not None else rs_7
    macro_sig = macro_to_signal(cycle_mode)
    # BTC itself: no RS edge vs self → macro-only
    if sym == "BTC":
        rs_sig = 0.0
        score = macro_sig
        w_m, w_r = 1.0, 0.0
    else:
        rs_sig = rs_to_signal(rs_primary, scale=rs_scale)
        w_m, w_r = w_macro, w_rs
        score = w_m * macro_sig + w_r * rs_sig

    label = score_label(score)
    ready = rs_primary is not None or sym == "BTC"

    explain = _explain(
        sym, cycle_mode, macro_sig, rs_30, rs_7, rs_sig, score, label, w_m, w_r
    )

    return {
        "symbol": sym,
        "ready": ready,
        "return_7d": None if ret_7 is None else round(ret_7, 4),
        "return_30d": None if ret_30 is None else round(ret_30, 4),
        "btc_return_7d": None if btc_7 is None else round(btc_7, 4),
        "btc_return_30d": None if btc_30 is None else round(btc_30, 4),
        "rs_7d": None if rs_7 is None else round(rs_7, 4),
        "rs_30d": None if rs_30 is None else round(rs_30, 4),
        "macro_mode": cycle_mode,
        "macro_signal": round(macro_sig, 3),
        "rs_signal": round(rs_sig, 3),
        "w_macro": w_m,
        "w_rs": w_r,
        "asset_risk_score": round(score, 3),
        "label": label,
        "explain": explain,
    }


def _pct(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:+.1f}%"


def _explain(
    sym: str,
    cycle_mode: str,
    macro_sig: float,
    rs_30: Optional[float],
    rs_7: Optional[float],
    rs_sig: float,
    score: float,
    label: str,
    w_m: float,
    w_r: float,
) -> str:
    rs_txt = _pct(rs_30 if rs_30 is not None else rs_7)
    window = "30d" if rs_30 is not None else "7d"
    if sym == "BTC":
        return (
            f"BTC macro: {cycle_mode} (signal {macro_sig:+.2f}) | "
            f"BTC has no RS vs self | asset signal: {label}"
        )
    despite = ""
    if label == "accumulate" and macro_sig <= 0:
        despite = " | accumulate despite soft/neutral/bear macro"
    elif label == "reduce" and macro_sig > 0:
        despite = " | lagging BTC despite bullish macro"
    return (
        f"BTC macro: {cycle_mode} (signal {macro_sig:+.2f}, w={w_m:.2f}) | "
        f"{sym} relative strength: {rs_txt} vs BTC ({window}, w={w_r:.2f}) | "
        f"score={score:+.2f} → asset signal: {label}{despite}"
    )


def build_portfolio_asset_momentum(
    closes_by_symbol: Dict[str, Sequence[float]],
    *,
    cycle_mode: str = "unknown",
    btc_symbol: str = "BTC",
    w_macro: float = W_MACRO,
    w_rs: float = W_RS,
) -> List[Dict[str, Any]]:
    """Build AssetMomentum rows for every symbol that has closes; requires BTC series."""
    btc = closes_by_symbol.get(btc_symbol) or closes_by_symbol.get("BTC")
    if not btc:
        return []
    out: List[Dict[str, Any]] = []
    for sym, closes in closes_by_symbol.items():
        if not closes:
            continue
        out.append(
            build_asset_momentum(
                sym,
                closes,
                btc,
                cycle_mode=cycle_mode,
                w_macro=w_macro,
                w_rs=w_rs,
            )
        )
    out.sort(key=lambda r: r.get("asset_risk_score", 0))
    return out


def fetch_binance_daily_closes(symbol: str, limit: int = 40) -> List[float]:
    """Public Binance daily closes for SYMBOLUSDT (no keys)."""
    sym = symbol.upper().replace("/", "")
    if not sym.endswith("USDT"):
        sym = f"{sym}USDT"
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={sym}&interval=1d&limit={limit}"
    )
    with urllib.request.urlopen(url, timeout=12) as resp:
        raw = json.loads(resp.read())
    return [float(row[4]) for row in raw]


def fetch_closes_for_symbols(
    symbols: Sequence[str],
    *,
    limit: int = 40,
    include_btc: bool = True,
) -> Dict[str, List[float]]:
    """Best-effort daily closes; skips failures."""
    wanted = {s.upper() for s in symbols if s}
    if include_btc:
        wanted.add("BTC")
    out: Dict[str, List[float]] = {}
    for sym in sorted(wanted):
        try:
            out[sym] = fetch_binance_daily_closes(sym, limit=limit)
        except Exception as exc:  # noqa: BLE001
            print(f"RS fetch error {sym}: {exc}")
    return out
