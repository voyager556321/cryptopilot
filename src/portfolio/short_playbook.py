"""Optional news-short experiment with written, unattended exits (advice only).

Spot wallet cannot short. If the user opens a Binance USD-M / margin short,
this module names the three exits in advance and, once tracked, says EXIT NOW
with the criterion that hit. No auto-orders.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


TAKE_PROFIT_PCT = 0.04
STOP_LOSS_PCT = 0.025
TIME_STOP_HOURS = 24
MAX_SIZE_USDT = 100.0
EQUITY_RISK_PCT = 0.01  # 1% of spot equity, capped
MIN_SIZE_USDT = 25.0
MAX_OPEN = 1
PREFERRED_SYMBOL = "BTC"
MAX_LEVERAGE = 2  # isolated only; size_usdt is notional, not margin
# BTCUSDT-M min qty is 0.001 BTC → notional ≈ price * 0.001 (error was 62.94 USDT)
MIN_BTC_QTY = 0.001
MIN_NOTIONAL_BUFFER = 1.02


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def suggested_size_usdt(equity_usdt: Optional[float]) -> float:
    if not equity_usdt or equity_usdt <= 0:
        return 50.0
    return round(min(MAX_SIZE_USDT, max(MIN_SIZE_USDT, float(equity_usdt) * EQUITY_RISK_PCT)), 2)


def exchange_min_notional(symbol: str, entry_price: float) -> float:
    """Smallest Binance USD-M notional we can actually send."""
    if (symbol or "").upper() == "BTC" and entry_price > 0:
        return round(float(entry_price) * MIN_BTC_QTY * MIN_NOTIONAL_BUFFER, 2)
    return 70.0


def first_try_notional(symbol: str, entry_price: float, equity_usdt: Optional[float]) -> float:
    """Half-size if the exchange allows it; otherwise the min 0.001 BTC (etc.)."""
    plan = suggested_size_usdt(equity_usdt)
    half = round(plan / 2.0, 2)
    floor = exchange_min_notional(symbol, entry_price)
    return round(max(half, floor), 2)


def short_pnl_pct(entry: float, mark: float) -> float:
    if entry <= 0:
        return 0.0
    return (entry - mark) / entry


def exit_prices(entry: float, *, tp_pct: float, sl_pct: float) -> Dict[str, float]:
    return {
        "take_profit_price": round(entry * (1.0 - tp_pct), 8),
        "stop_loss_price": round(entry * (1.0 + sl_pct), 8),
    }


def pick_alert(alerts: List[dict]) -> Optional[dict]:
    """One idea only. Prefer BTC. Ignore WATCH (already dumped)."""
    shorts = [a for a in (alerts or []) if a.get("action") == "ALERT_SHORT"]
    if not shorts:
        return None
    for a in shorts:
        if (a.get("symbol") or "").upper() == PREFERRED_SYMBOL:
            return a
    return shorts[0]


def priced_in_watch(alerts: List[dict]) -> Optional[dict]:
    watches = [a for a in (alerts or []) if a.get("action") == "WATCH"]
    for a in watches:
        if (a.get("symbol") or "").upper() == PREFERRED_SYMBOL:
            return a
    return watches[0] if watches else None


def idea_from_alert(
    alert: dict,
    *,
    equity_usdt: Optional[float] = None,
    tp_pct: float = TAKE_PROFIT_PCT,
    sl_pct: float = STOP_LOSS_PCT,
    time_stop_hours: int = TIME_STOP_HOURS,
) -> dict:
    entry = float(alert.get("price") or 0)
    px = exit_prices(entry, tp_pct=tp_pct, sl_pct=sl_pct) if entry > 0 else {
        "take_profit_price": 0.0,
        "stop_loss_price": 0.0,
    }
    size = suggested_size_usdt(equity_usdt)
    symbol = (alert.get("symbol") or "").upper()
    first = first_try_notional(symbol, entry, equity_usdt)
    margin_2x = round(first / MAX_LEVERAGE, 2)
    sl_usd = round(first * sl_pct, 2)
    tp_usd = round(first * tp_pct, 2)
    return {
        "status": "idea",
        "venue": "binance_futures_or_margin",
        "not_spot": True,
        "symbol": symbol,
        "entry_price": entry,
        "size_usdt": first,
        "half_size_usdt": first,
        "plan_size_usdt": size,
        "leverage": MAX_LEVERAGE,
        "isolated": True,
        "take_profit_pct": tp_pct,
        "stop_loss_pct": sl_pct,
        "time_stop_hours": time_stop_hours,
        **px,
        "news_title": alert.get("news_title") or "",
        "news_url": alert.get("news_url") or "",
        "headline": (
            f"Optional {symbol} short · first try ${first:.0f} notional at {MAX_LEVERAGE}x isolated "
            f"(~${margin_2x:.0f} margin). Binance min is 0.001 BTC. Not the spot wallet."
        ),
        "checklist": [
            "This is Binance USD-M isolated — not a spot SELL of your bag.",
            f"One coin only ({symbol}). Do not spray ETH/SOL/ZEC with the same news.",
            f"First try: ${first:.0f} notional at {MAX_LEVERAGE}x isolated (~${margin_2x:.0f} margin). "
            f"Ideal half of ${size:.0f} is below Binance min (0.001 BTC), so use the floor — do not add more.",
            "Size is notional (exposure). 2x must not double the dollar risk.",
            f"BEFORE entry: stop-market at {px['stop_loss_price']:.4g} "
            f"(price +{sl_pct:.1%}, not ${sl_pct*100:.1f} and not Binance ROI%). "
            f"On ${first:.0f} notional that is about ${sl_usd:.2f} loss "
            f"(−{sl_pct * MAX_LEVERAGE:.1%} of the ${margin_2x:.0f} margin at {MAX_LEVERAGE}x). "
            "If you cannot place this order, skip.",
            f"Take-profit limit at {px['take_profit_price']:.4g} "
            f"(price −{tp_pct:.1%} ≈ +${tp_usd:.2f} on ${first:.0f} notional). "
            f"On Binance set the trigger by mark price, not by '2.5% ROI' — at {MAX_LEVERAGE}x that would fire twice too early.",
            f"Time stop: close at market in {time_stop_hours}h even if TP/SL did not fill. "
            "News edge dies; do not sit on the chart.",
            "Never move the stop further away. Never add. No cross margin.",
        ],
        "rules": _rule_rows(
            entry=entry,
            mark=entry,
            pnl_pct=0.0,
            elapsed_h=0.0,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            time_stop_hours=time_stop_hours,
            tp_price=px["take_profit_price"],
            sl_price=px["stop_loss_price"],
            deadline_at=None,
            hit_reason=None,
            notional_usdt=first,
        ),
    }


def evaluate_position(
    pos: dict,
    mark_price: Optional[float],
    now: Optional[datetime] = None,
) -> dict:
    now = now or _now()
    entry = float(pos.get("entry_price") or 0)
    tp_pct = float(pos.get("take_profit_pct") or TAKE_PROFIT_PCT)
    sl_pct = float(pos.get("stop_loss_pct") or STOP_LOSS_PCT)
    hours = float(pos.get("time_stop_hours") or TIME_STOP_HOURS)
    opened = _parse_dt(pos["opened_at"])
    elapsed_h = max(0.0, (now - opened).total_seconds() / 3600.0)
    remaining_h = max(0.0, hours - elapsed_h)
    deadline = opened + timedelta(hours=hours)
    mark = float(mark_price) if mark_price and mark_price > 0 else None
    pnl_pct = short_pnl_pct(entry, mark) if mark else 0.0
    px = exit_prices(entry, tp_pct=tp_pct, sl_pct=sl_pct) if entry > 0 else {
        "take_profit_price": 0.0,
        "stop_loss_price": 0.0,
    }

    reason = None
    if mark is not None:
        if pnl_pct <= -sl_pct:
            reason = "stop_loss"
        elif pnl_pct >= tp_pct:
            reason = "take_profit"
        elif elapsed_h >= hours:
            reason = "time_stop"
    elif elapsed_h >= hours:
        reason = "time_stop"

    status = "exit" if reason else "hold"
    symbol = (pos.get("symbol") or "").upper()
    headlines = {
        "stop_loss": (
            f"EXIT NOW · {symbol} short · stop-loss. Price rose "
            f"+{sl_pct:.1%} from entry. Close; do not wait or add."
        ),
        "take_profit": (
            f"EXIT NOW · {symbol} short · take-profit. Move proceeds to USDT. "
            "Do not reverse into a long on the same news."
        ),
        "time_stop": (
            f"EXIT NOW · {symbol} short · {hours:.0f}h time-stop. "
            "News edge is gone. Close at market even if PnL is tiny."
        ),
    }
    if status == "hold":
        headline = (
            f"HOLD {symbol} short · {remaining_h:.1f}h left on the clock. "
            "Do not watch ticks. Next check: time-stop, or if SL/TP already filled on the exchange."
        )
    else:
        headline = headlines[reason]

    out = {
        **pos,
        "status": status,
        "exit_reason": reason,
        "headline": headline,
        "mark_price": mark,
        "unrealized_pnl_pct": round(pnl_pct, 4) if mark else None,
        "elapsed_hours": round(elapsed_h, 2),
        "remaining_hours": round(remaining_h, 2),
        "deadline_at": deadline.isoformat(timespec="seconds"),
        **px,
        "rules": _rule_rows(
            entry=entry,
            mark=mark or entry,
            pnl_pct=pnl_pct if mark else 0.0,
            elapsed_h=elapsed_h,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            time_stop_hours=hours,
            tp_price=px["take_profit_price"],
            sl_price=px["stop_loss_price"],
            deadline_at=deadline.isoformat(timespec="seconds"),
            hit_reason=reason,
            notional_usdt=float(pos.get("size_usdt") or 0),
        ),
        "checklist": _live_checklist(status, reason, remaining_h, px, sl_pct, tp_pct, hours),
    }
    return out


def _live_checklist(
    status: str,
    reason: Optional[str],
    remaining_h: float,
    px: dict,
    sl_pct: float,
    tp_pct: float,
    hours: float,
) -> List[str]:
    if status == "exit":
        if reason == "stop_loss":
            return [
                f"Close the futures/margin short now. SL was {px['stop_loss_price']:.4g}.",
                "Do not average. Do not flip long on the same headline.",
                "Then press “I closed it” so this card stops yelling.",
            ]
        if reason == "take_profit":
            return [
                f"Close now (or confirm the TP limit filled) at {px['take_profit_price']:.4g}.",
                "Keep proceeds in USDT today.",
                "Then press “I closed it”.",
            ]
        return [
            f"{hours:.0f}h elapsed — close at market. This is the unattended rule.",
            "Tiny red or green is still an exit. The news trade is over.",
            "Then press “I closed it”.",
        ]
    return [
        f"Stop must already be working on the exchange at {px['stop_loss_price']:.4g} (+{sl_pct:.1%}).",
        f"TP limit at {px['take_profit_price']:.4g} (−{tp_pct:.1%}).",
        f"If neither fills, close in {remaining_h:.1f}h. Do not sit on the chart.",
        "One position. No add. Spot bag stays untouched.",
    ]


def _rule_rows(
    *,
    entry: float,
    mark: float,
    pnl_pct: float,
    elapsed_h: float,
    tp_pct: float,
    sl_pct: float,
    time_stop_hours: float,
    tp_price: float,
    sl_price: float,
    deadline_at: Optional[str],
    hit_reason: Optional[str],
    notional_usdt: float = 0.0,
) -> List[dict]:
    def state(key: str, hit: bool) -> str:
        if hit_reason == key:
            return "HIT — exit"
        if hit:
            return "HIT — exit"
        return "waiting"

    sl_hit = hit_reason == "stop_loss" or pnl_pct <= -sl_pct
    tp_hit = hit_reason == "take_profit" or pnl_pct >= tp_pct
    tm_hit = hit_reason == "time_stop" or elapsed_h >= time_stop_hours
    sl_usd = round(notional_usdt * sl_pct, 2) if notional_usdt else None
    tp_usd = round(notional_usdt * tp_pct, 2) if notional_usdt else None
    sl_extra = f" · ≈ ${sl_usd:.2f} on notional (at {MAX_LEVERAGE}x = −{sl_pct * MAX_LEVERAGE:.1%} of margin)" if sl_usd is not None else ""
    tp_extra = f" · ≈ +${tp_usd:.2f} on notional (at {MAX_LEVERAGE}x = +{tp_pct * MAX_LEVERAGE:.1%} of margin)" if tp_usd is not None else ""
    return [
        {
            "id": "stop_loss",
            "name": "Stop-loss (must be an exchange order)",
            "trigger": f"Mark price ≥ {sl_price:.4g}  (+{sl_pct:.1%} from {entry:.4g}){sl_extra}",
            "why": "2.5% is a price move, not $2.50. Set the stop by mark price, not Binance ROI%.",
            "state": state("stop_loss", sl_hit),
        },
        {
            "id": "take_profit",
            "name": "Take-profit",
            "trigger": f"Mark price ≤ {tp_price:.4g}  (−{tp_pct:.1%} from {entry:.4g}){tp_extra}",
            "why": "4% is a price drop, not $4. Bank it; do not hunt a crash.",
            "state": state("take_profit", tp_hit),
        },
        {
            "id": "time_stop",
            "name": "Time-stop (the unattended rule)",
            "trigger": (
                f"{time_stop_hours:.0f}h from entry"
                + (f" · deadline {deadline_at.replace('T', ' ')[:19]} UTC" if deadline_at else "")
            ),
            "why": "If TP/SL did not fire, the headline edge is gone. Close anyway.",
            "state": state("time_stop", tm_hit),
        },
    ]


def build_short_playbook(
    *,
    alerts: List[dict],
    prices: Dict[str, float],
    tracked_open: Optional[dict],
    equity_usdt: Optional[float],
    tp_pct: float = TAKE_PROFIT_PCT,
    sl_pct: float = STOP_LOSS_PCT,
    time_stop_hours: int = TIME_STOP_HOURS,
    now: Optional[datetime] = None,
) -> dict:
    now = now or _now()
    if tracked_open:
        sym = (tracked_open.get("symbol") or "").upper()
        mark = prices.get(sym)
        evaluated = evaluate_position(tracked_open, mark, now=now)
        return {
            "mode": evaluated["status"],  # hold | exit
            "has_position": True,
            "position": evaluated,
            "idea": None,
            "headline": evaluated["headline"],
            "checklist": evaluated["checklist"],
            "rules": evaluated["rules"],
            "note": (
                "Advice only — the dashboard does not close Binance futures. "
                "If the stop was not placed on the exchange, place/close it now."
            ),
        }

    alert = pick_alert(alerts)
    if alert:
        idea = idea_from_alert(
            alert,
            equity_usdt=equity_usdt,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            time_stop_hours=time_stop_hours,
        )
        return {
            "mode": "idea",
            "has_position": False,
            "position": None,
            "idea": idea,
            "headline": idea["headline"],
            "checklist": idea["checklist"],
            "rules": idea["rules"],
            "note": (
                "Optional experiment, not a command. Default remains the spot plan above. "
                "If you open it, press “I'm in” so this card can tell you when to exit."
            ),
        }

    watch = priced_in_watch(alerts)
    if watch:
        sym = (watch.get("symbol") or "").upper()
        return {
            "mode": "skip",
            "has_position": False,
            "position": None,
            "idea": None,
            "headline": (
                f"Do not short {sym} — already down in 24h, likely priced in. "
                "Default is the spot plan (don't add)."
            ),
            "checklist": [
                "Chasing a dump with a late short is how time-stops bleed.",
                "Keep the spot bag. No futures.",
            ],
            "rules": [],
            "note": watch.get("news_title") or "",
        }

    return {
        "mode": "idle",
        "has_position": False,
        "position": None,
        "idea": None,
        "headline": "No short today. The spot plan above is the default.",
        "checklist": [
            "A short is optional futures, never the spot wallet.",
            f"If you ever take one: 1 coin, half notional at {MAX_LEVERAGE}x isolated, "
            f"SL on the exchange, {TIME_STOP_HOURS}h clock. Do not use 2x to double size.",
        ],
        "rules": [],
        "note": "",
    }


class ShortWatch:
    """User-tracked shorts (you opened them). Not auto-paper."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "short_watch.json"
        self._data: Dict[str, Any] = {"open": [], "closed": []}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            self._data.setdefault("open", [])
            self._data.setdefault("closed", [])
        except Exception:
            pass

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def open_one(self, payload: dict) -> dict:
        if self._data["open"]:
            raise ValueError("Already tracking a short. Close it before opening another.")
        symbol = (payload.get("symbol") or "").upper()
        entry = float(payload.get("entry_price") or 0)
        if not symbol or entry <= 0:
            raise ValueError("symbol and entry_price required")
        size = float(payload.get("size_usdt") or suggested_size_usdt(None))
        if size > MAX_SIZE_USDT:
            size = MAX_SIZE_USDT
        tp = float(payload.get("take_profit_pct") or TAKE_PROFIT_PCT)
        sl = float(payload.get("stop_loss_pct") or STOP_LOSS_PCT)
        hours = int(payload.get("time_stop_hours") or TIME_STOP_HOURS)
        px = exit_prices(entry, tp_pct=tp, sl_pct=sl)
        opened_at = payload.get("opened_at") or _now().isoformat(timespec="seconds")
        pos = {
            "id": str(uuid.uuid4())[:8],
            "opened_at": opened_at,
            "symbol": symbol,
            "side": "short",
            "venue": "binance_futures_or_margin",
            "entry_price": entry,
            "size_usdt": round(size, 2),
            "take_profit_pct": tp,
            "stop_loss_pct": sl,
            "time_stop_hours": hours,
            **px,
            "source": payload.get("source") or payload.get("news_title") or "",
        }
        self._data["open"].append(pos)
        self.save()
        return pos

    def close(self, pos_id: str, *, reason: str = "manual") -> dict:
        kept = []
        closed = None
        for p in self._data["open"]:
            if p.get("id") == pos_id:
                closed = {**p, "status": "closed", "closed_at": _now().isoformat(timespec="seconds"), "close_reason": reason}
            else:
                kept.append(p)
        if closed is None:
            raise ValueError("short not found")
        self._data["open"] = kept
        self._data["closed"] = (self._data.get("closed") or [])[-50:] + [closed]
        self.save()
        return closed

    def current(self) -> Optional[dict]:
        opens = self._data.get("open") or []
        return opens[0] if opens else None
