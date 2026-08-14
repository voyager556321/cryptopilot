"""IBKR stock sleeve targets + action hints (advice only)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Percent of total account (incl. cash)
SLEEVE_TARGETS: Dict[str, float] = {
    "core": 30.0,       # AAPL AMZN GOOG NVDA NFLX
    "core_etf": 15.0,   # CSPX / broad market
    "semi": 12.0,       # MU (cap — currently overweight)
    "ai_etf": 8.0,      # WTAI
    "quantum": 10.0,    # QBTS IONQ QTUM combined
    "spec_etf": 5.0,    # SPCX ROKT
    "theme_etf": 5.0,   # CIBR EVX
    "cash": 15.0,
}

# Soft per-name caps (% of portfolio) to stop lottery concentration
NAME_CAPS: Dict[str, float] = {
    "MU": 12.0,
    "QBTS": 5.0,   # aggressive swing — hard size limit
    "IONQ": 4.0,
    "SPCX": 3.0,
    "ROKT": 3.0,
    "WTAI": 8.0,
}

MIN_ACTION_USD = 5.0  # tiny account — still skip dust

# Friend-style swing: buy meaningful dips, sell most (not all) into strength
SWING_BUY_DIP_PCT = -12.0       # unrealized vs cost ≤ this → candidate buy
SWING_SELL_GAIN_PCT = 25.0      # unrealized vs cost ≥ this → trim most of bag
SWING_TRIM_PCT_OF_BAG = 0.60    # sell ~60% of position into strength (keep runner)
SWING_ADD_USD_MIN = 15.0        # "нормальна сума" на акаунт ~$250–300
SWING_ADD_USD_MAX = 40.0
SWING_ADD_PCT_OF_CASH = 0.35    # use up to 35% of cash per add
CORE_BUY_OK = {"core", "core_etf", "semi", "ai_etf", "theme_etf", "spec_etf", "quantum"}


def swing_playbook(snapshot: dict) -> Dict[str, Any]:
    """
    Friend style:
      - when something drops meaningfully vs your cost → buy a normal chunk (from cash)
      - when it runs → sell most of the bag, keep a runner
    """
    total = float(snapshot.get("total_usd") or 0)
    cash = float(snapshot.get("cash_usd") or 0)
    cash_pct = float(snapshot.get("cash_pct") or 0)
    holdings = list(snapshot.get("holdings") or [])

    buys: List[dict] = []
    sells: List[dict] = []

    add_budget = min(SWING_ADD_USD_MAX, max(SWING_ADD_USD_MIN, cash * SWING_ADD_PCT_OF_CASH))
    can_buy = cash_pct >= 12.0 and cash >= SWING_ADD_USD_MIN

    for h in holdings:
        unr_pct = float(h.get("unrealized_pnl_pct") or 0)
        mv = float(h.get("market_value") or 0)
        sym = h["symbol"]
        tag = h.get("tag") or "other"
        cap = NAME_CAPS.get(sym)
        pct = float(h.get("pct") or 0)

        # Sell strength: big green vs cost → trim majority, keep runner
        if unr_pct >= SWING_SELL_GAIN_PCT and mv >= MIN_ACTION_USD:
            sell_usd = round(mv * SWING_TRIM_PCT_OF_BAG, 2)
            sells.append({
                "symbol": sym,
                "action": "SELL",
                "unrealized_pct": unr_pct,
                "amount_usd": sell_usd,
                "pct_of_bag": round(SWING_TRIM_PCT_OF_BAG * 100, 0),
                "keep_usd": round(mv - sell_usd, 2),
                "note": (
                    f"+{unr_pct:.0f}% vs cost → продай ~{SWING_TRIM_PCT_OF_BAG:.0%} бага "
                    f"(${sell_usd:.0f}), залиш runner ~${mv - sell_usd:.0f}"
                ),
            })

        # Buy dip: meaningful red vs cost, only if cash ok and under name cap
        if unr_pct <= SWING_BUY_DIP_PCT and tag in CORE_BUY_OK:
            if not can_buy:
                continue
            if cap is not None and pct >= cap:
                continue
            room = None if cap is None else max(0.0, total * (cap - pct) / 100.0)
            add = add_budget if room is None else min(add_budget, room)
            if add < SWING_ADD_USD_MIN * 0.8:
                continue
            buys.append({
                "symbol": sym,
                "action": "BUY",
                "unrealized_pct": unr_pct,
                "amount_usd": round(add, 2),
                "note": (
                    f"{unr_pct:.0f}% vs cost → докуп нормальну суму ~${add:.0f} "
                    f"(з cash, не all-in)"
                ),
            })

    sells.sort(key=lambda x: -x["unrealized_pct"])
    buys.sort(key=lambda x: x["unrealized_pct"])  # deepest dip first

    return {
        "style": "friend_swing",
        "rules": [
            f"Падіння ≤ {SWING_BUY_DIP_PCT:.0f}% від твого cost → BUY нормальну суму "
            f"(${SWING_ADD_USD_MIN:.0f}–{SWING_ADD_USD_MAX:.0f}, з cash)",
            f"Ріст ≥ +{SWING_SELL_GAIN_PCT:.0f}% від cost → SELL ~{SWING_TRIM_PCT_OF_BAG:.0%} позиції, runner лишай",
            "Не купуй, якщо cash < 12% — спочатку підніми подушку trim’ами",
            "Не доливай вище name cap (MU/quantum)",
            "Одна ідея = один ордер нормального розміру, не 10× по $5",
            "Гібрид: краще вхід на відкоті до EMA (див. секцію нижче), не на піку",
        ],
        "can_buy": can_buy,
        "cash_usd": round(cash, 2),
        "cash_pct": cash_pct,
        "add_budget_usd": round(add_budget, 2) if can_buy else 0.0,
        "buys": buys,
        "sells": sells,
        "headline": (
            "Swing як у друга: докуп на нормальному мінусі vs cost, "
            "у плюсі продавай більшу частину, не все."
            if can_buy
            else (
                f"Cash {cash_pct:.1f}% замало для докупів. "
                "Спочатку trim переможців / overweight → потім лови просадки."
            )
        ),
    }


def sleeve_allocation(snapshot: dict) -> List[dict]:
    total = float(snapshot.get("total_usd") or 0)
    sleeve = dict(snapshot.get("sleeve_pct") or {})
    sleeve.setdefault("cash", float(snapshot.get("cash_pct") or 0))
    rows = []
    for name, target in SLEEVE_TARGETS.items():
        cur = float(sleeve.get(name) or 0)
        gap = cur - target
        value = total * cur / 100.0 if total else 0
        rows.append({
            "sleeve": name,
            "current_pct": round(cur, 2),
            "target_pct": target,
            "gap_pct": round(gap, 2),
            "value_usd": round(value, 2),
        })
    rows.sort(key=lambda r: abs(r["gap_pct"]), reverse=True)
    return rows


def rebalance_hints(snapshot: dict) -> Dict[str, Any]:
    total = float(snapshot.get("total_usd") or 0)
    holdings = list(snapshot.get("holdings") or [])
    actionable: List[dict] = []
    minor: List[dict] = []

    # Name caps
    for h in holdings:
        sym = h["symbol"]
        cap = NAME_CAPS.get(sym)
        if cap is None:
            continue
        pct = float(h.get("pct") or 0)
        if pct <= cap * 1.15:  # 15% relative slack
            continue
        overflow_pct = pct - cap
        amount = total * overflow_pct / 100.0
        entry = {
            "asset": sym,
            "action": "SELL",
            "current_pct": pct,
            "target_pct": cap,
            "deviation_pct": round((pct - cap) / cap * 100, 1) if cap else 0,
            "amount_usd": round(-amount, 2),
            "note": f"Over name cap {cap:.0f}% — trim ~${amount:.0f} (concentration)",
        }
        if amount >= MIN_ACTION_USD:
            actionable.append(entry)
        else:
            entry["action"] = "HOLD"
            minor.append(entry)

    # Underwater high-fee dust / weak thesis — prefer trim into cash when red
    for h in holdings:
        mv = float(h.get("market_value") or 0)
        unr = float(h.get("unrealized_pnl") or 0)
        tag = h.get("tag")
        if tag in {"spec_etf", "quantum"} and unr < -1.5 and mv >= MIN_ACTION_USD:
            actionable.append({
                "asset": h["symbol"],
                "action": "SELL",
                "current_pct": h.get("pct"),
                "target_pct": 0,
                "deviation_pct": 0,
                "amount_usd": round(-min(mv * 0.5, mv), 2),
                "note": "Underwater satellite — partial trim to raise cash (optional)",
            })

    # Cash too low
    cash_pct = float(snapshot.get("cash_pct") or 0)
    if cash_pct < SLEEVE_TARGETS["cash"] - 5 and total:
        need = total * (SLEEVE_TARGETS["cash"] - cash_pct) / 100.0
        actionable.append({
            "asset": "CASH",
            "action": "RAISE",
            "current_pct": cash_pct,
            "target_pct": SLEEVE_TARGETS["cash"],
            "deviation_pct": round(cash_pct - SLEEVE_TARGETS["cash"], 2),
            "amount_usd": round(need, 2),
            "note": f"Cash {cash_pct:.1f}% < {SLEEVE_TARGETS['cash']:.0f}% — trim winners/satellites",
        })

    # Too many tiny lines
    tiny = [h for h in holdings if float(h.get("market_value") or 0) < 8]
    if len(tiny) >= 5:
        minor.append({
            "asset": "MANY",
            "action": "CONSOLIDATE",
            "current_pct": 0,
            "target_pct": 0,
            "deviation_pct": 0,
            "amount_usd": 0,
            "note": f"{len(tiny)} positions under $8 — fees eat edge; merge into CSPX/core",
        })

    actionable.sort(key=lambda x: abs(float(x.get("amount_usd") or 0)), reverse=True)
    return {
        "policy": (
            "IBKR: cap names (esp. MU), keep ~15% cash, consolidate dust into CSPX/core. "
            "Advice only — no auto orders."
        ),
        "actionable": actionable,
        "minor": minor,
        "allocation": sleeve_allocation(snapshot),
        "targets": SLEEVE_TARGETS,
        "name_caps": NAME_CAPS,
        "needs_rebalance": bool(actionable),
    }


def build_ibkr_action_plan(snapshot: dict) -> Dict[str, Any]:
    daily = snapshot.get("daily_pnl_usd")
    cash_pct = float(snapshot.get("cash_pct") or 0)
    holdings = list(snapshot.get("holdings") or [])
    total = float(snapshot.get("total_usd") or 0)

    # Prefer trimming high-flyer / satellite winners first
    def score(h: dict) -> float:
        tag = h.get("tag")
        mv = float(h.get("market_value") or 0)
        unr = float(h.get("unrealized_pnl") or 0)
        s = mv
        if tag in {"quantum", "spec_etf", "semi"}:
            s *= 1.5
        if unr > 0:
            s *= 1.2
        if tag in {"core", "core_etf"}:
            s *= 0.25
        return s

    ranked = sorted(holdings, key=score, reverse=True)
    actions: List[dict] = []
    mode = "hold"
    checklist: List[str] = []

    if daily is not None and daily >= 1.5:
        lock = round(float(daily) * 0.30, 2)
        left = lock
        mode = "profit_lock"
        headline = (
            f"IBKR сьогодні +${daily:.2f}. Зафіксуй ~30% ≈ ${lock:.2f} у USD cash "
            f"(спочатку satellite / MU overweight)."
        )
        for h in ranked:
            if left < 1:
                break
            mv = float(h["market_value"])
            chunk = min(left, mv * 0.35, mv)
            if chunk < 1:
                continue
            actions.append({
                "symbol": h["symbol"],
                "sell_usd": round(chunk, 2),
                "pct_of_bag": round(chunk / mv * 100, 1),
                "reason": f"{h.get('tag')} trim → cash",
            })
            left -= chunk
        checklist = [
            f"Продай ≈ ${lock:.2f} сумарно",
            "Залиш у USD (не реінвестуй одразу в QBTS/IONQ)",
            f"Cash зараз {cash_pct:.1f}% — ціль ~15%+",
        ]
    elif daily is not None and daily <= -3.0:
        cap = max(5.0, min(abs(float(daily)) * 0.25, total * 0.04 if total else 5))
        mode = "defense"
        headline = (
            f"IBKR сьогодні ${daily:.2f}. Захист: зменши ризик ≈ ${cap:.2f} "
            f"(spec/quantum першими, core майже не чіпай)."
        )
        left = cap
        for h in ranked:
            if h.get("tag") in {"core", "core_etf"}:
                continue
            if left < 1:
                break
            mv = float(h["market_value"])
            chunk = min(left, mv * 0.4, mv)
            if chunk < 1:
                continue
            actions.append({
                "symbol": h["symbol"],
                "sell_usd": round(chunk, 2),
                "pct_of_bag": round(chunk / mv * 100, 1),
                "reason": "defense trim",
            })
            left -= chunk
        checklist = [
            "Не average-down по quantum/spec сьогодні",
            "Стоп нових покупок до завтра",
            f"Піднімай cash (зараз {cash_pct:.1f}%)",
        ]
    else:
        headline = "Немає обов’язкової дії по daily PnL — дивись rebalance / caps."
        checklist = [
            f"Cash {cash_pct:.1f}% · total ${total:,.2f} · {snapshot.get('positions_count', 0)} позицій",
            "Не відкривай нові $5 ticket’и — консолідуй",
            "MU: якщо >>12% портфеля — частковий trim у CSPX/cash",
        ]

    return {
        "mode": mode,
        "headline": headline,
        "actions": actions,
        "checklist": checklist,
        "note": "IBKR advice only. Live TWS/Client Portal sync — наступний крок.",
        "rules": {
            "profit_lock": "Daily ≥ +$1.5 → lock ~30% у USD",
            "defense": "Daily ≤ −$3 → trim satellites",
            "structure": "15% cash · MU cap 12% · менше дрібних ліній",
        },
    }
