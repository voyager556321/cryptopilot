"""Profit-lock and defensive exit action plan for the local UI (advice only)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


CORE = {"BTC", "ETH"}
STABLES = {"USDT", "USDC", "FDUSD", "BUSD", "TUSD", "DAI"}
# Gold / ballast — do not trim for profit-lock / defense first
GOLD = {"PAXG", "XAUT", "PAX"}
# Prefer trimming these satellites when locking daily PnL (ahead of SOL/BNB)
TRIM_FIRST = {"AAVE", "LINK", "FIL", "XRP"}
TRIM_MID = {"ZEC", "SOL", "BNB"}

# --- Tunable profit-lock / drawdown gates (Task 1) ---
LOCK_PCT_DEFAULT = 0.30
LOCK_TRIGGER_USDT = 10.0
LOCK_TRIGGER_PCT = 0.003  # 0.3% of equity also qualifies as "green day"
MIN_LOCK_CHUNK_USDT = 5.0
DEFENSE_TRIGGER_USDT = -50.0
DEFENSE_LOCK_PCT = 0.20

# Drawdown gate: block lock while in significant/deep DD unless recovering
DRAWDOWN_THRESHOLD_30 = -0.08   # −8% from 30d peak → "in drawdown"
RECOVERY_BOUNCE_MIN = 0.03      # +3% from 30d trough
RECOVERY_LOCK_SCALE = 0.50      # half-size locks while recovering inside DD
ALIGN_7D_MIN_PCT = -0.02        # block weak 1D if 7D worse than −2%

# Task 2: asset momentum blend (also in relative_strength.py — keep in sync for docs)
W_MACRO = 0.40
W_RS = 0.60


def _holdings(portfolio: dict) -> List[dict]:
    if isinstance(portfolio.get("holdings"), list) and portfolio["holdings"]:
        return list(portfolio["holdings"])
    out = []
    for sym, info in (portfolio.get("assets") or {}).items():
        out.append({
            "symbol": sym,
            "value_usdt": float(info.get("value_usdt") or 0),
            "pct": float(info.get("pct") or 0),
            "quantity": info.get("quantity"),
            "price_usdt": info.get("price_usdt"),
            "asset_class": info.get("asset_class") or ("stable" if sym in STABLES else "crypto"),
        })
    return out


def _trim_candidates(
    holdings: List[dict],
    asset_signals: Optional[Dict[str, dict]] = None,
) -> List[dict]:
    """Prefer cutting alts / satellites first; protect BTC/ETH and gold.

    Asset RS layer (Task 2): bump trim priority for ``reduce``, lower for ``accumulate``.
    Does not change profit-lock/drawdown gates — only sell ordering.
    """
    signals = asset_signals or {}
    scored = []
    for h in holdings:
        sym = (h.get("symbol") or "").upper()
        if sym in STABLES:
            continue
        if sym in GOLD:
            continue  # never suggest trimming gold for lock/defense
        value = float(h.get("value_usdt") or 0)
        if value < 5:
            continue
        # Higher score = sell first
        score = value
        if sym in CORE:
            score *= 0.15  # protect core
        elif sym in TRIM_FIRST:
            score *= 2.5  # AAVE / LINK / FIL / XRP first
        elif sym in TRIM_MID:
            score *= 1.1
        else:
            score *= 1.3
        label = (signals.get(sym) or {}).get("label")
        if label == "reduce":
            score *= 1.35
        elif label == "accumulate":
            score *= 0.55
        scored.append({**h, "symbol": sym, "trim_score": score, "rs_label": label})
    scored.sort(key=lambda x: -x["trim_score"])
    return scored


def _allocate_sells(amount_usdt: float, candidates: List[dict]) -> List[dict]:
    remaining = max(0.0, float(amount_usdt))
    sells: List[dict] = []
    for c in candidates:
        if remaining < 5:
            break
        value = float(c.get("value_usdt") or 0)
        chunk = min(remaining, value * 0.40, value)
        if chunk < 5:
            continue
        sym = c["symbol"]
        rs_label = c.get("rs_label")
        if sym in CORE:
            reason = "core trim (small)"
        elif sym in TRIM_FIRST:
            reason = "satellite trim (AAVE/alts; gold protected)"
        else:
            reason = "alt trim (gold protected)"
        if rs_label:
            reason = f"{reason} · RS:{rs_label}"
        sells.append({
            "symbol": sym,
            "sell_usdt": round(chunk, 2),
            "pct_of_bag": round(chunk / value * 100, 1) if value else 0,
            "reason": reason,
        })
        remaining -= chunk
    return sells


def _pct_txt(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:+.1f}%"


def _usd_txt(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    sign = "+" if x > 0 else ""
    return f"{sign}${x:.2f}"


def _resolve_pnl_context(history: dict) -> Dict[str, Any]:
    """Prefer explicit pnl_context; synthesize from legacy today/7d/24h fields."""
    ctx = history.get("pnl_context")
    if isinstance(ctx, dict) and ctx.get("h1d"):
        return ctx

    today = history.get("today_pnl") or {}
    h24 = history.get("pnl_24h") or today
    h7 = history.get("pnl_7d") or {}
    h30 = history.get("pnl_30d") or {}
    current = history.get("current_total")

    def _h(window: str, src: dict) -> dict:
        abs_v = src.get("abs")
        pct_v = src.get("pct")
        return {
            "window": window,
            "abs": abs_v,
            "pct": pct_v,
            "ready": abs_v is not None,
            "base": None,
            "current": current,
        }

    return {
        "current_total": current,
        "h1d": _h("1d", h24 if h24.get("abs") is not None else today),
        "h7d": _h("7d", h7),
        "h30d": _h("30d", h30),
        "drawdown": history.get("drawdown") or {
            "dd_30_pct": None,
            "dd_90_pct": None,
            "bounce_from_30d_low_pct": None,
            "in_drawdown": False,
            "depth": "none",
        },
        "today_pnl": today,
        "pnl_24h": h24,
        "pnl_7d": h7,
        "pnl_30d": h30,
    }


def profit_lock_gate(
    ctx: Dict[str, Any],
    *,
    recovery_bounce_min: float = RECOVERY_BOUNCE_MIN,
    align_7d_min_pct: float = ALIGN_7D_MIN_PCT,
) -> Tuple[bool, bool, List[str]]:
    """
    Returns (allowed, recovering, reasons).

    allowed=False → skip profit-lock (still in active drawdown without recovery).
    recovering=True → allow but typically scale lock size.
    """
    reasons: List[str] = []
    dd = ctx.get("drawdown") or {}
    h1d = ctx.get("h1d") or {}
    h7d = ctx.get("h7d") or {}
    h30d = ctx.get("h30d") or {}

    reasons.append(
        f"1D {_usd_txt(h1d.get('abs'))} ({_pct_txt(h1d.get('pct'))}) · "
        f"7D {_usd_txt(h7d.get('abs'))} ({_pct_txt(h7d.get('pct'))}) · "
        f"30D {_usd_txt(h30d.get('abs'))} ({_pct_txt(h30d.get('pct'))})"
    )
    reasons.append(
        f"DD30={_pct_txt(dd.get('dd_30_pct'))} · DD90={_pct_txt(dd.get('dd_90_pct'))} · "
        f"depth={dd.get('depth') or 'none'}"
    )

    bounce = dd.get("bounce_from_30d_low_pct")
    h7_abs = h7d.get("abs")
    recovering = (
        bool(dd.get("in_drawdown"))
        and bounce is not None
        and bounce >= recovery_bounce_min
        and h7d.get("ready")
        and h7_abs is not None
        and h7_abs >= 0
    )

    if dd.get("in_drawdown") and not recovering:
        reasons.append(
            "still in active drawdown, profit-lock skipped "
            f"(bounce_from_low={_pct_txt(bounce)} < {_pct_txt(recovery_bounce_min)} "
            "or 7D not non-negative)"
        )
        return False, False, reasons

    if recovering:
        reasons.append(
            f"portfolio recovering from {_pct_txt(dd.get('dd_30_pct'))} drawdown "
            f"(bounce_from_low={_pct_txt(bounce)})"
        )

    # Weak 1D inside a clearly red week
    h1_pct = h1d.get("pct")
    h7_pct = h7d.get("pct")
    if (
        h7d.get("ready")
        and h7_pct is not None
        and h7_pct < align_7d_min_pct
        and h1_pct is not None
        and h1_pct < 0.01
    ):
        reasons.append(
            f"1D gain too weak vs negative 7D ({_pct_txt(h7_pct)}); lock skipped"
        )
        return False, recovering, reasons

    if not dd.get("in_drawdown"):
        reasons.append("drawdown below threshold — profit-lock available")

    return True, recovering, reasons


def build_action_plan(
    portfolio: dict,
    history: Optional[dict] = None,
    *,
    lock_pct: float = LOCK_PCT_DEFAULT,
    lock_trigger_usdt: float = LOCK_TRIGGER_USDT,
    defense_trigger_usdt: float = DEFENSE_TRIGGER_USDT,
    defense_lock_pct: float = DEFENSE_LOCK_PCT,
    market_cycle: Optional[dict] = None,
    already_locked_usdt: float = 0.0,
    asset_closes: Optional[Dict[str, List[float]]] = None,
    asset_momentum: Optional[List[dict]] = None,
    w_macro: float = W_MACRO,
    w_rs: float = W_RS,
) -> Dict[str, Any]:
    """
    Advice-only plan:
    - green day + drawdown gate: lock lock_pct of 1D PnL into USDT
    - BTC cycle = portfolio conservatism only (not hard sell-all)
    - asset RS momentum = per-asset accumulate/hold/reduce layer
    """
    from src.portfolio.relative_strength import build_portfolio_asset_momentum

    history = history or {}
    cycle = market_cycle or {}
    cycle_mode = cycle.get("mode") or "unknown"
    already = max(0.0, float(already_locked_usdt or 0))

    # Portfolio-level macro: conservatism only
    if cycle_mode in {"bounce_watch", "risk_off"}:
        lock_pct = max(lock_pct, 0.35)
        lock_trigger_usdt = min(lock_trigger_usdt, 8.0)

    ctx = _resolve_pnl_context(history)
    h1d = ctx.get("h1d") or {}
    today = history.get("today_pnl") or {"abs": h1d.get("abs"), "pct": h1d.get("pct")}
    today_abs = today.get("abs")
    if today_abs is None:
        today_abs = h1d.get("abs")
    today_pct = today.get("pct")
    if today_pct is None:
        today_pct = h1d.get("pct")
    d24 = (history.get("pnl_24h") or h1d).get("abs")

    holdings = _holdings(portfolio)

    momentum_rows: List[dict] = list(asset_momentum or [])
    if not momentum_rows and asset_closes:
        momentum_rows = build_portfolio_asset_momentum(
            asset_closes,
            cycle_mode=cycle_mode,
            w_macro=w_macro,
            w_rs=w_rs,
        )
    signal_by_sym = {r["symbol"]: r for r in momentum_rows if r.get("symbol")}

    candidates = _trim_candidates(holdings, signal_by_sym)
    total = float(portfolio.get("total_usdt") or 0)
    stable_pct = float(portfolio.get("stable_pct") or 0)
    usdt_target = 25.0 if cycle_mode in {"bounce_watch", "risk_off"} else 20.0

    actions: List[dict] = []
    mode = "hold"
    headline = "No required action — stick to the plan, don't improvise."
    checklist: List[str] = []
    lock_target = 0.0
    lock_remaining = 0.0

    green_day = False
    if today_abs is not None and today_abs >= lock_trigger_usdt:
        green_day = True
    elif (
        today_pct is not None
        and today_pct >= LOCK_TRIGGER_PCT
        and today_abs is not None
        and today_abs > 0
    ):
        green_day = True

    allowed, recovering, gate_reasons = profit_lock_gate(ctx)

    if green_day:
        if not allowed:
            mode = "hold"
            headline = (
                f"Today {_usd_txt(today_abs)}. Still in active drawdown — "
                f"profit-lock skipped."
            )
            checklist = gate_reasons + [
                "Wait for recovery (bounce from 30d low + non-negative 7D) "
                "or for DD30 to heal above threshold",
                f"USDT {stable_pct:.1f}% · target ≥{usdt_target:.0f}%",
            ]
        else:
            lock_target = round(float(today_abs) * lock_pct, 2)
            if recovering:
                lock_target = round(lock_target * RECOVERY_LOCK_SCALE, 2)
            lock_remaining = round(max(0.0, lock_target - already), 2)
            if lock_remaining < MIN_LOCK_CHUNK_USDT:
                mode = "hold"
                headline = (
                    f"Today {_usd_txt(today_abs)}. Profit-lock done: "
                    f"${already:.2f} / target ${lock_target:.2f}. No more trimming needed."
                )
                checklist = gate_reasons + [
                    f"Locked today ${already:.2f} USDT",
                    "Don't redeploy locked USDT into alts today",
                ]
                actions = []
            else:
                sells = _allocate_sells(lock_remaining, candidates)
                mode = "profit_lock"
                recover_note = " (recovery-scaled)" if recovering else ""
                headline = (
                    f"Today {_usd_txt(today_abs)}. Lock ~${lock_remaining:.2f} more into USDT"
                    f"{recover_note} "
                    f"(target {lock_pct:.0%}=${lock_target:.2f}, already ${already:.2f})."
                )
                checklist = gate_reasons + [
                    f"Sell ≈ ${lock_remaining:.2f} more (already locked ${already:.2f})",
                    "Keep proceeds in USDT today (don't reinvest immediately)",
                    "Don't add new alts after locking",
                    "After the order, click Detect from Binance",
                ]
                actions = sells

    elif today_abs is not None and today_abs <= defense_trigger_usdt:
        raw = abs(today_abs) * defense_lock_pct
        cap = max(25.0, min(raw, total * 0.03 if total else raw))
        sells = _allocate_sells(cap, candidates)
        mode = "defense"
        headline = (
            f"Today ${today_abs:.2f}. Defense mode: reduce risk ≈ ${cap:.2f} "
            f"via alts first (not a panic all-sell)."
        )
        actions = sells
        checklist = [
            "Trim OTHER/alts first; leave BTC/ETH almost untouched",
            f"Sell cap now ≈ ${cap:.2f} (avoid crushing the book / burning fees)",
            "Use limit or several small markets — not one huge dump",
            "After that — stop new buys until tomorrow",
            "If the day is already ≤ −2% of portfolio — don't trade more today",
        ] + gate_reasons[:2]

    elif d24 is not None and d24 < -30 and (today_abs is None or today_abs < 0):
        mode = "caution"
        headline = (
            f"24h ${d24:.2f}. Don't average down. Keep USDT, wait for a setup."
        )
        checklist = [
            "No average-down on alts",
            "New entries only on a clear setup (otherwise skip)",
            f"USDT now {stable_pct:.1f}% — cushion target ≥{usdt_target:.0f}%",
        ] + gate_reasons[:2]

    else:
        checklist = gate_reasons + [
            "No strong daily edge — don't touch the portfolio just to act",
            "Follow setups (grid/news/rebalance), not emotions",
            f"USDT {stable_pct:.1f}% · target ≥{usdt_target:.0f}% · total ${total:,.2f}",
        ]
        if already > 0:
            checklist.insert(0, f"Already locked today ${already:.2f}")
        if today_abs is not None and today_abs < 0 and allowed:
            checklist.insert(
                0,
                "Profit-lock remains available when 1D turns green "
                "(drawdown not blocking)",
            )

    if cycle.get("available") or cycle_mode != "unknown":
        checklist.append(
            f"Portfolio macro (BTC): {cycle_mode} — tunes lock/USDT conservatism only, "
            f"not a hard sell-all"
        )
        if cycle.get("headline"):
            checklist.append(f"Macro detail: {str(cycle.get('headline'))[:120]}")

    for row in sorted(
        momentum_rows,
        key=lambda r: abs(float(r.get("asset_risk_score") or 0)),
        reverse=True,
    )[:6]:
        if row.get("explain"):
            checklist.append(row["explain"])

    dd = ctx.get("drawdown") or {}
    return {
        "mode": mode,
        "headline": headline,
        "today_pnl_usdt": today_abs,
        "today_pnl_pct": today_pct,
        "pnl_24h_usdt": d24,
        "pnl_context": {
            "h1d": ctx.get("h1d"),
            "h7d": ctx.get("h7d"),
            "h30d": ctx.get("h30d"),
            "drawdown": dd,
            "lock_allowed": allowed,
            "recovering": recovering,
        },
        "asset_signals": momentum_rows,
        "risk_layers": {
            "portfolio_macro": cycle_mode,
            "w_macro": w_macro,
            "w_rs": w_rs,
            "note": (
                "asset_risk_score = w_macro*btc_macro_signal + w_rs*rs_signal; "
                "does not override drawdown profit-lock gate"
            ),
        },
        "lock_pct": lock_pct,
        "lock_trigger_usdt": lock_trigger_usdt,
        "lock_target_usdt": lock_target,
        "already_locked_usdt": round(already, 2),
        "lock_remaining_usdt": lock_remaining,
        "suggested_lock_usdt": lock_remaining if mode == "profit_lock" else 0.0,
        "actions": actions,
        "checklist": checklist,
        "cycle_mode": cycle_mode,
        "rules": {
            "profit_lock": (
                f"If 1D PnL ≥ ${lock_trigger_usdt:.0f} (or ≥{LOCK_TRIGGER_PCT:.1%}) "
                f"AND (DD30 > {DRAWDOWN_THRESHOLD_30:.0%} OR recovering) "
                f"→ sell {lock_pct:.0%} of 1D PnL into USDT"
            ),
            "example": (
                "Green 1D inside deep DD without recovery → skip. "
                "Green 1D while recovering from trough → partial lock."
            ),
            "asset_momentum": (
                f"Per-asset score = {w_macro:.2f}*BTC_macro + {w_rs:.2f}*RS_vs_BTC; "
                "labels accumulate/hold/reduce — advice only"
            ),
            "defense": (
                f"If daily PnL ≤ ${defense_trigger_usdt:.0f} → defensive trim "
                f"~{defense_lock_pct:.0%} of |loss|, alts first"
            ),
            "min_impact": (
                "Don't sell everything at once: ≤40% of one coin per step; "
                "don't trim PAXG/gold; core BTC/ETH last"
            ),
            "cycle": (
                "BTC macro only widens/narrows lock urgency and USDT cushion; "
                "strong RS alts can still show accumulate under neutral/bear macro"
            ),
        },
        "note": (
            "Advice for manual spot orders only. The bot does not place orders. "
            "After a manual trim, click Detect from Binance, or sync will suggest the full amount again."
        ),
    }
