"""Hybrid swing + positional style hints for IBKR holdings (advice only)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.news.equity_fetch import fetch_yahoo_ohlcv

# Trading-style verdicts (not Buffett long-term investing)
ASSET_VERDICTS: Dict[str, dict] = {
    "CIBR": {
        "grade": "fit",
        "label": "Чудово підходить",
        "horizon": "1–3 міс.",
        "why": "Секторальний ETF кібербезпеки — ліквідні імена, чіткі тренди, зручний TA.",
        "max_pct": 8.0,
        "style": "positional_etf",
    },
    "QTUM": {
        "grade": "fit",
        "label": "Чудово підходить",
        "horizon": "1–3 міс.",
        "why": "Quantum/AI ETF — імпульс + структура тренду для утримання тижнів–місяців.",
        "max_pct": 6.0,
        "style": "positional_etf",
    },
    "ROKT": {
        "grade": "caution",
        "label": "Обережно",
        "horizon": "свінг / короткий позиційний",
        "why": "Космос/ВПК залежить від замовлень і геополітики; тренди рвані, вихід важчий.",
        "max_pct": 3.0,
        "style": "cautious_etf",
    },
    "QBTS": {
        "grade": "extreme",
        "label": "Екстремальний ризик",
        "horizon": "3–7 днів свінг",
        "why": "Мала капіталізація / speculative — ±50% швидко. Жорсткий SL, ≤2–5% депо.",
        "max_pct": 5.0,
        "style": "aggressive_swing",
    },
    "IONQ": {
        "grade": "extreme",
        "label": "Високий ризик",
        "horizon": "короткий свінг",
        "why": "Квантова single-name — волатильність як у QBTS; ліміт розміру.",
        "max_pct": 4.0,
        "style": "aggressive_swing",
    },
    "SPCX": {
        "grade": "caution",
        "label": "Обережно",
        "horizon": "свінг",
        "why": "Спекулятивний theme ETF — імпульс ок, але не роздувай частку.",
        "max_pct": 3.0,
        "style": "cautious_etf",
    },
    "WTAI": {
        "grade": "fit",
        "label": "Ок для гібриду",
        "horizon": "тижні–місяці",
        "why": "AI ETF — тренд/імпульс; вхід краще на відкоті до EMA, не на FOMO-піку.",
        "max_pct": 8.0,
        "style": "positional_etf",
    },
    "MU": {
        "grade": "fit",
        "label": "Імпульс / semi",
        "horizon": "свінг–позиційний",
        "why": "Сильний momentum у semi; тримай name cap (~12%), не average-down без сетапу.",
        "max_pct": 12.0,
        "style": "momentum",
    },
    "NVDA": {
        "grade": "fit",
        "label": "Core momentum",
        "horizon": "тижні–місяці",
        "why": "Ліквідний тренд; відкоти до EMA20/50 — робочі зони входу.",
        "max_pct": 10.0,
        "style": "momentum",
    },
    "AAPL": {
        "grade": "core",
        "label": "Core / якір",
        "horizon": "позиційний",
        "why": "Менша волатильність за quantum — якір портфеля, не лотерея.",
        "max_pct": 15.0,
        "style": "core",
    },
    "AMZN": {
        "grade": "core",
        "label": "Core",
        "horizon": "позиційний",
        "why": "Core tech — тримай як базу, свінг-докупи на глибоких відкотах.",
        "max_pct": 12.0,
        "style": "core",
    },
    "GOOG": {
        "grade": "core",
        "label": "Core",
        "horizon": "позиційний",
        "why": "Core — менше трейдити, більше тримати за трендом.",
        "max_pct": 10.0,
        "style": "core",
    },
    "NFLX": {
        "grade": "fit",
        "label": "Momentum ok",
        "horizon": "свінг–позиційний",
        "why": "Трендовий імпульс; не пересиджуй без trailing stop.",
        "max_pct": 8.0,
        "style": "momentum",
    },
    "CSPX": {
        "grade": "core",
        "label": "Broad market якір",
        "horizon": "позиційний",
        "why": "S&P UCITS — місце для консолідації dust / стабільності рукава.",
        "max_pct": 20.0,
        "style": "core_etf",
    },
    "EVX": {
        "grade": "caution",
        "label": "Тема / малий розмір",
        "horizon": "свінг",
        "why": "Нішевий theme — ок маленькою лінією, не роздувай.",
        "max_pct": 3.0,
        "style": "theme",
    },
}

DEFAULT_VERDICT = {
    "grade": "neutral",
    "label": "Без спец-вердикту",
    "horizon": "свінг",
    "why": "Оцінюй по тренду / EMA і size vs cash.",
    "max_pct": 5.0,
    "style": "generic",
}

HYBRID_RULES = [
    "Вхід на відкотах: не купуй на піку тренду — чекай ціну біля EMA20 або EMA50.",
    "Утримання за трендом: якщо пішло вгору — trailing stop, тримай тижні, не фіксуй на 3-й день.",
    "Spec (QBTS/IONQ): ≤2–5% депо на угоду; секторальні ETF (CIBR/QTUM) — більший розмір.",
    "ROKT/SPCX: обережний розмір; не average-down без чіткого сетапу.",
    "Один сетап = один нормальний ордер; без дрібних $5 ticket’ів.",
]


def _signal_from_ema(
    dist20: Optional[float],
    dist50: Optional[float],
    *,
    grade: str,
) -> dict:
    """Classify pullback / extended / ok based on distance to EMAs (%)."""
    if dist20 is None and dist50 is None:
        return {
            "signal": "no_data",
            "note": "Немає Yahoo bars для EMA",
        }

    d20 = dist20 if dist20 is not None else 99.0
    d50 = dist50 if dist50 is not None else 99.0

    # Near EMA = pullback zone
    near20 = abs(d20) <= 2.5
    near50 = abs(d50) <= 3.5
    above_both = d20 > 0 and d50 > 0
    below50 = d50 < -1.0

    if grade == "extreme":
        if near20 or near50:
            return {
                "signal": "swing_entry_watch",
                "note": "Spec біля EMA — лише малий розмір + жорсткий SL (3–7д свінг)",
            }
        if d20 > 8:
            return {
                "signal": "too_extended",
                "note": "Spec далеко над EMA20 — не chase; чекай відкіт",
            }
        return {
            "signal": "hold_tight",
            "note": "Spec: тримай лише з trailing / готовим виходом",
        }

    if near20 or near50:
        which = "EMA20" if near20 else "EMA50"
        return {
            "signal": "pullback_buy_zone",
            "note": f"Відкіт до {which} — зона входу для гібриду (не FOMO-пік)",
        }
    if d20 > 6 and above_both:
        return {
            "signal": "trail_hold",
            "note": "Розтягнуто над EMA — не докуповуй; trailing stop, дай тренду жити",
        }
    if below50 and grade in {"fit", "core", "caution"}:
        return {
            "signal": "deeper_dip",
            "note": "Нижче EMA50 — або сильніший сетап / або skip (не average blindly)",
        }
    return {
        "signal": "trend_ok",
        "note": "Ціна в робочій зоні відносно EMA — дивись об’єм і новини",
    }


def analyze_symbol(symbol: str, holding: Optional[dict] = None) -> dict:
    sym = symbol.upper()
    verdict = {**DEFAULT_VERDICT, **(ASSET_VERDICTS.get(sym) or {})}
    chart = fetch_yahoo_ohlcv(sym, interval="1d", range_="6mo")
    pct = float((holding or {}).get("pct") or 0)
    unr = (holding or {}).get("unrealized_pnl_pct")
    over_cap = pct > float(verdict.get("max_pct") or 100)

    sig = _signal_from_ema(
        chart.get("dist_ema20_pct"),
        chart.get("dist_ema50_pct"),
        grade=str(verdict.get("grade") or "neutral"),
    )

    return {
        "symbol": sym,
        "grade": verdict["grade"],
        "label": verdict["label"],
        "horizon": verdict["horizon"],
        "why": verdict["why"],
        "style": verdict["style"],
        "max_pct": verdict["max_pct"],
        "portfolio_pct": round(pct, 2),
        "over_cap": over_cap,
        "unrealized_pct": unr,
        "last": chart.get("last"),
        "ema20": chart.get("ema20_last"),
        "ema50": chart.get("ema50_last"),
        "dist_ema20_pct": chart.get("dist_ema20_pct"),
        "dist_ema50_pct": chart.get("dist_ema50_pct"),
        "signal": sig["signal"],
        "signal_note": sig["note"],
        "chart_ok": bool(chart.get("available")),
        "error": chart.get("error"),
    }


def hybrid_playbook(snapshot: dict, *, with_charts: bool = True) -> Dict[str, Any]:
    """
    Hybrid swing + positional advice for current IBKR holdings.
    with_charts=True hits Yahoo per symbol (slower) — use for Refresh / dedicated endpoint.
    """
    holdings = list(snapshot.get("holdings") or [])
    rows: List[dict] = []

    if with_charts:
        for h in holdings:
            sym = (h.get("symbol") or "").upper()
            if not sym:
                continue
            try:
                rows.append(analyze_symbol(sym, h))
            except Exception as e:
                v = {**DEFAULT_VERDICT, **(ASSET_VERDICTS.get(sym) or {})}
                rows.append({
                    "symbol": sym,
                    "grade": v["grade"],
                    "label": v["label"],
                    "horizon": v["horizon"],
                    "why": v["why"],
                    "style": v["style"],
                    "max_pct": v["max_pct"],
                    "portfolio_pct": float(h.get("pct") or 0),
                    "over_cap": False,
                    "signal": "error",
                    "signal_note": str(e),
                    "chart_ok": False,
                    "error": str(e),
                })
    else:
        for h in holdings:
            sym = (h.get("symbol") or "").upper()
            v = {**DEFAULT_VERDICT, **(ASSET_VERDICTS.get(sym) or {})}
            pct = float(h.get("pct") or 0)
            rows.append({
                "symbol": sym,
                "grade": v["grade"],
                "label": v["label"],
                "horizon": v["horizon"],
                "why": v["why"],
                "style": v["style"],
                "max_pct": v["max_pct"],
                "portfolio_pct": round(pct, 2),
                "over_cap": pct > float(v["max_pct"]),
                "unrealized_pct": h.get("unrealized_pnl_pct"),
                "signal": "pending",
                "signal_note": "Натисни Refresh EMA — підтягне Yahoo daily + EMA20/50",
                "chart_ok": False,
            })

    # Priority: pullback zones and over_cap first
    order = {
        "pullback_buy_zone": 0,
        "swing_entry_watch": 1,
        "deeper_dip": 2,
        "too_extended": 3,
        "trail_hold": 4,
        "over_cap": 5,
    }
    rows.sort(key=lambda r: (
        0 if r.get("over_cap") else 1,
        order.get(r.get("signal") or "", 9),
        -float(r.get("portfolio_pct") or 0),
    ))

    pullbacks = [r for r in rows if r.get("signal") in {"pullback_buy_zone", "swing_entry_watch"}]
    extended = [r for r in rows if r.get("signal") in {"too_extended", "trail_hold"}]
    caution = [r for r in rows if r.get("grade") in {"extreme", "caution"}]

    return {
        "style": "hybrid_swing_positional",
        "headline": (
            "Гібрид: вхід на відкоті до EMA, утримання за трендом тижнями, "
            "spec — малий розмір."
        ),
        "rules": HYBRID_RULES,
        "assets": rows,
        "pullback_candidates": [r["symbol"] for r in pullbacks],
        "extended": [r["symbol"] for r in extended],
        "caution_names": [r["symbol"] for r in caution],
        "note": "Advice only · Yahoo daily EMA · не авто-ордери",
    }
