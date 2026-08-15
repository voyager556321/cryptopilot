"""Walk historical days through production ``build_action_plan``."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from src.portfolio.action_plan import build_action_plan
from src.portfolio.history import build_pnl_context
from src.portfolio.market_cycle import assess_market_cycle

from .data import (
    DailySnapshot,
    btc_close_by_date,
    daily_returns,
    load_btc_bars,
    load_daily_snapshots,
)
from .journal import attach_forward_returns, summarize_action_forwards
from .metrics import StrategyMetrics, compare_strategies, compute_metrics
from .portfolio_sim import (
    apply_lock,
    apply_risk_return,
    portfolio_from_sleeves,
    sleeves_from_state,
)


@dataclass
class BacktestResult:
    journal: List[Dict[str, Any]]
    action_forward_summary: Dict[str, Any]
    equity: Dict[str, List[Dict[str, Any]]]
    metrics: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


def _history_payload(series: List[Dict[str, Any]], current: float) -> Dict[str, Any]:
    """Mimic PortfolioHistory.overview fields consumed by build_action_plan."""
    now = datetime.now(timezone.utc)
    if series:
        last_ts = series[-1].get("timestamp")
        try:
            now = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    ctx = build_pnl_context(series, current, now=now)
    # Calendar today_pnl ≈ h1d for daily backtest steps
    h1 = ctx.get("h1d") or {}
    today = {"abs": h1.get("abs"), "pct": h1.get("pct")}
    return {
        "points": len(series),
        "series": series[-120:],
        "current_total": current,
        "today_pnl": today,
        "pnl_24h": today,
        "pnl_7d": {
            "abs": (ctx.get("h7d") or {}).get("abs"),
            "pct": (ctx.get("h7d") or {}).get("pct"),
        },
        "pnl_30d": {
            "abs": (ctx.get("h30d") or {}).get("abs"),
            "pct": (ctx.get("h30d") or {}).get("pct"),
        },
        "pnl_context": ctx,
        "note": "backtest",
    }


def _bars_until(bars: Sequence[dict], day: str) -> List[dict]:
    return [b for b in bars if str(b.get("date") or "") <= day]


def run_action_plan_backtest(
    snapshots: Sequence[DailySnapshot],
    *,
    btc_bars: Optional[Sequence[dict]] = None,
    usdt_heavy_pct: float = 50.0,
    alt_beta: float = 1.25,
    execute_locks: bool = True,
) -> BacktestResult:
    """
    Run the production action plan day-by-day.

    Strategies compared on the **same** BTC return path:
      - lockin: follow suggested_lock_usdt on profit_lock/defense
      - buy_hold: initial sleeves, no locks
      - usdt_heavy: start with ``usdt_heavy_pct`` cash, no locks
    """
    snaps = list(snapshots)
    if len(snaps) < 3:
        raise ValueError("Need at least 3 daily snapshots for a backtest")

    bars = list(btc_bars or [])
    closes = btc_close_by_date(bars)
    dates = [s.date for s in snaps]
    rets = daily_returns(closes, dates)

    # --- initial sleeve dollars from first historical snapshot ---
    s0 = snaps[0]
    total0 = float(s0.total_usdt)
    cp_be = total0 * s0.btc_eth_pct / 100.0
    cp_al = total0 * s0.alts_pct / 100.0
    cp_us = total0 * s0.stable_pct / 100.0

    bh_be, bh_al, bh_us = cp_be, cp_al, cp_us

    heavy = max(0.0, min(95.0, float(usdt_heavy_pct))) / 100.0
    risk0 = total0 * (1.0 - heavy)
    # Keep same be/alts mix inside risk sleeve
    risk_mix_be = (s0.btc_eth_pct / max(s0.btc_eth_pct + s0.alts_pct, 1e-9))
    uh_us = total0 * heavy
    uh_be = risk0 * risk_mix_be
    uh_al = risk0 - uh_be

    journal: List[Dict[str, Any]] = []
    eq_cp: List[Dict[str, Any]] = []
    eq_bh: List[Dict[str, Any]] = []
    eq_uh: List[Dict[str, Any]] = []
    series_cp: List[Dict[str, Any]] = []

    locks = 0
    locked_total = 0.0
    trades = 0
    already_locked_today = 0.0
    last_day = ""

    for i, snap in enumerate(snaps):
        day = snap.date
        if day != last_day:
            already_locked_today = 0.0
            last_day = day

        # Apply overnight BTC return before deciding (except day 0)
        r = float(rets.get(day) or 0.0) if i > 0 else 0.0
        if i > 0:
            cp_be, cp_al, cp_us = apply_risk_return(cp_be, cp_al, cp_us, r, alt_beta=alt_beta)
            bh_be, bh_al, bh_us = apply_risk_return(bh_be, bh_al, bh_us, r, alt_beta=alt_beta)
            uh_be, uh_al, uh_us = apply_risk_return(uh_be, uh_al, uh_us, r, alt_beta=alt_beta)

        sleeves = sleeves_from_state(cp_be, cp_al, cp_us)
        portfolio = portfolio_from_sleeves(
            total_usdt=sleeves["total_usdt"],
            btc_eth_pct=sleeves["btc_eth_pct"],
            stable_pct=sleeves["stable_pct"],
            alts_pct=sleeves["alts_pct"],
        )

        point = {"timestamp": f"{day}T23:59:00+00:00", "total_usdt": sleeves["total_usdt"]}
        series_cp.append(point)
        hist = _history_payload(series_cp, sleeves["total_usdt"])

        cycle = assess_market_cycle(
            bars=_bars_until(bars, day),
            stable_pct=sleeves["stable_pct"],
            fetch=False,
        )

        plan = build_action_plan(
            portfolio,
            hist,
            market_cycle=cycle,
            already_locked_usdt=already_locked_today,
            # No live RS in backtest — ordering falls back to sleeve heuristics
            asset_closes=None,
        )

        mode = str(plan.get("mode") or "hold")
        suggested = float(plan.get("suggested_lock_usdt") or 0)
        filled = 0.0
        if execute_locks and mode in ("profit_lock", "defense") and suggested > 0:
            cp_be, cp_al, cp_us, filled = apply_lock(cp_be, cp_al, cp_us, suggested)
            if filled > 0:
                locks += 1
                locked_total += filled
                trades += len(plan.get("actions") or []) or 1
                already_locked_today += filled
                # refresh series last point after lock
                sleeves = sleeves_from_state(cp_be, cp_al, cp_us)
                series_cp[-1] = {
                    "timestamp": f"{day}T23:59:00+00:00",
                    "total_usdt": sleeves["total_usdt"],
                }

        reasons = list(plan.get("checklist") or [])[:6]
        if plan.get("headline"):
            reasons = [str(plan["headline"])] + reasons

        journal.append({
            "date": day,
            "portfolio_value": round(sleeves["total_usdt"], 2),
            "daily_pnl": (hist.get("today_pnl") or {}).get("abs"),
            "btc_regime": cycle.get("mode"),
            "usdt_percent": round(sleeves["stable_pct"], 2),
            "action": mode.upper(),
            "reason": reasons,
            "amount_to_lock": round(suggested, 2),
            "amount_locked_sim": round(filled, 2),
            "lock_remaining_usdt": plan.get("lock_remaining_usdt"),
            "cycle_available": bool(cycle.get("available")),
        })

        eq_cp.append({"date": day, "equity": round(sleeves_from_state(cp_be, cp_al, cp_us)["total_usdt"], 2)})
        eq_bh.append({"date": day, "equity": round(sleeves_from_state(bh_be, bh_al, bh_us)["total_usdt"], 2)})
        eq_uh.append({"date": day, "equity": round(sleeves_from_state(uh_be, uh_al, uh_us)["total_usdt"], 2)})

    # Forward returns on LockIn equity path
    eq_map = {r["date"]: float(r["equity"]) for r in eq_cp}
    journal = attach_forward_returns(journal, eq_map, dates)
    fwd_summary = summarize_action_forwards(journal)

    cp_curve = [r["equity"] for r in eq_cp]
    bh_curve = [r["equity"] for r in eq_bh]
    uh_curve = [r["equity"] for r in eq_uh]
    bh_end = bh_curve[-1] if bh_curve else None

    m_cp = compute_metrics(
        "lockin",
        cp_curve,
        profit_locks=locks,
        locked_usdt_total=locked_total,
        trades=trades,
        buy_hold_end=bh_end,
    )
    m_bh = compute_metrics("buy_hold", bh_curve)
    m_uh = compute_metrics("usdt_heavy", uh_curve, buy_hold_end=bh_end)

    return BacktestResult(
        journal=journal,
        action_forward_summary=fwd_summary,
        equity={
            "lockin": eq_cp,
            "buy_hold": eq_bh,
            "usdt_heavy": eq_uh,
        },
        metrics=compare_strategies([m_cp, m_bh, m_uh]),
        meta={
            "days": len(snaps),
            "start": snaps[0].date,
            "end": snaps[-1].date,
            "usdt_heavy_pct": usdt_heavy_pct,
            "alt_beta": alt_beta,
            "execute_locks": execute_locks,
            "engine": "src.portfolio.action_plan.build_action_plan",
            "limitation": (
                "Holdings reconstructed from sleeve % (BTC/ETH/alts/USDT). "
                "Same build_action_plan() as production; no LLM."
            ),
        },
    )


def run_from_files(
    history_csv: str,
    *,
    btc_cache: Optional[str] = None,
    fetch_btc: bool = True,
    **kwargs: Any,
) -> BacktestResult:
    snaps = load_daily_snapshots(history_csv)
    bars = load_btc_bars(cache_path=btc_cache, fetch=fetch_btc)
    return run_action_plan_backtest(snaps, btc_bars=bars, **kwargs)
