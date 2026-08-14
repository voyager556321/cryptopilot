"""Paper trading journal for strategy testing (no live orders)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_STABLES = {"USDT", "USDC", "FDUSD", "BUSD", "TUSD", "DAI"}


class PaperJournal:
    def __init__(self, output_dir: Path, bank_usdt: float = 5000.0, max_open: int = 5):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "paper_trades.json"
        self.bank_usdt = bank_usdt
        self.max_open = max_open
        self._data: Dict[str, Any] = {
            "bank_usdt": bank_usdt,
            "open": [],
            "closed": [],
        }
        self._load()
        self.drop_non_spot_opens()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _load(self):
        if not self.path.exists():
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            self._data.setdefault("open", [])
            self._data.setdefault("closed", [])
        except Exception:
            pass

    def save(self):
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def _has_open(self, symbol: str, side: str, strategy: str) -> bool:
        for p in self._data["open"]:
            if p["symbol"] == symbol and p["side"] == side and p["strategy"] == strategy:
                return True
        return False

    def open_from_news_alert(self, alert: dict) -> Optional[dict]:
        action = alert.get("action")
        if action != "ALERT":
            # Spot risk manager: never auto-open paper shorts (ALERT_SHORT)
            return None
        side = "long"
        symbol = alert["symbol"]
        if symbol in _STABLES:
            return None
        strategy = alert.get("strategy") or "news_dip"
        if self._has_open(symbol, side, strategy):
            return None
        if len(self._data["open"]) >= self.max_open:
            return None

        size = float(alert.get("suggested_size_usdt") or 0)
        if size <= 0:
            return None
        price = float(alert["price"])
        if price <= 0:
            return None

        pos = {
            "id": str(uuid.uuid4())[:8],
            "opened_at": self._now().isoformat(timespec="seconds"),
            "symbol": symbol,
            "side": side,
            "strategy": strategy,
            "entry_price": price,
            "size_usdt": size,
            "take_profit_pct": float(alert.get("take_profit_pct") or 0.04),
            "stop_loss_pct": float(alert.get("stop_loss_pct") or 0.025),
            "time_stop_hours": int(alert.get("time_stop_hours") or 24),
            "source": alert.get("news_title") or "",
            "status": "open",
            "mark_price": price,
            "unrealized_pnl_usdt": 0.0,
            "unrealized_pnl_pct": 0.0,
        }
        self._data["open"].append(pos)
        self.save()
        return pos

    def open_from_rebalance(self, hint: dict, fraction: float = 0.25) -> Optional[dict]:
        action = hint.get("action")
        if action != "BUY":
            # SELL / USDT "short" is not a spot-wallet action — skip paper
            return None
        side = "long"
        symbol = hint["asset"]
        if symbol in _STABLES:
            return None
        strategy = "rebalance"
        if self._has_open(symbol, side, strategy):
            return None
        if len(self._data["open"]) >= self.max_open:
            return None

        notional = abs(float(hint.get("amount_usdt") or 0)) * fraction
        if notional < 10:
            return None

        # Entry price unknown here — caller should pass price
        price = float(hint.get("price") or 0)
        if price <= 0:
            return None

        pos = {
            "id": str(uuid.uuid4())[:8],
            "opened_at": self._now().isoformat(timespec="seconds"),
            "symbol": symbol,
            "side": side,
            "strategy": strategy,
            "entry_price": price,
            "size_usdt": round(notional, 2),
            "take_profit_pct": 0.05,
            "stop_loss_pct": 0.03,
            "time_stop_hours": 168,  # week — rebalance is slow
            "source": hint.get("note") or f"rebalance {action}",
            "status": "open",
            "mark_price": price,
            "unrealized_pnl_usdt": 0.0,
            "unrealized_pnl_pct": 0.0,
        }
        self._data["open"].append(pos)
        self.save()
        return pos

    def drop_non_spot_opens(self) -> int:
        """Cancel paper shorts and stablecoin fills — they are not spot-wallet actions."""
        kept = []
        dropped = 0
        for pos in self._data.get("open") or []:
            if pos.get("side") == "short" or pos.get("symbol") in _STABLES:
                dropped += 1
                continue
            kept.append(pos)
        if dropped:
            self._data["open"] = kept
            self.save()
        return dropped

    def mark_to_market(self, prices: Dict[str, float]) -> dict:
        """Update open PnL; close on TP/SL/time-stop. prices: symbol -> price."""
        self.drop_non_spot_opens()
        still_open = []
        closed_now = []
        now = self._now()

        for pos in self._data["open"]:
            symbol = pos["symbol"]
            price = prices.get(symbol)
            if price is None or price <= 0:
                still_open.append(pos)
                continue

            entry = float(pos["entry_price"])
            size = float(pos["size_usdt"])
            if pos["side"] == "long":
                pnl_pct = (price - entry) / entry
            else:
                pnl_pct = (entry - price) / entry
            pnl_usdt = size * pnl_pct
            pos["mark_price"] = price
            pos["unrealized_pnl_usdt"] = round(pnl_usdt, 2)
            pos["unrealized_pnl_pct"] = round(pnl_pct, 4)

            tp = float(pos.get("take_profit_pct") or 0)
            sl = float(pos.get("stop_loss_pct") or 0)
            reason = None
            if tp and pnl_pct >= tp:
                reason = "take_profit"
            elif sl and pnl_pct <= -sl:
                reason = "stop_loss"
            else:
                try:
                    opened = datetime.fromisoformat(pos["opened_at"])
                    if opened.tzinfo is None:
                        opened = opened.replace(tzinfo=timezone.utc)
                    hours = float(pos.get("time_stop_hours") or 24)
                    if now - opened >= timedelta(hours=hours):
                        reason = "time_stop"
                except Exception:
                    pass

            if reason:
                pos["status"] = "closed"
                pos["closed_at"] = now.isoformat(timespec="seconds")
                pos["exit_price"] = price
                pos["realized_pnl_usdt"] = round(pnl_usdt, 2)
                pos["realized_pnl_pct"] = round(pnl_pct, 4)
                pos["close_reason"] = reason
                self._data["closed"].append(pos)
                closed_now.append(pos)
            else:
                still_open.append(pos)

        self._data["open"] = still_open
        self._data["closed"] = self._data["closed"][-200:]
        self.save()
        return self.summary()

    def summary(self) -> dict:
        self.drop_non_spot_opens()
        closed = self._data["closed"]
        realized = sum(float(p.get("realized_pnl_usdt") or 0) for p in closed)
        unrealized = sum(float(p.get("unrealized_pnl_usdt") or 0) for p in self._data["open"])
        wins = sum(1 for p in closed if float(p.get("realized_pnl_usdt") or 0) > 0)
        losses = sum(1 for p in closed if float(p.get("realized_pnl_usdt") or 0) < 0)
        by_strategy: Dict[str, float] = {}
        for p in closed:
            s = p.get("strategy") or "unknown"
            by_strategy[s] = by_strategy.get(s, 0.0) + float(p.get("realized_pnl_usdt") or 0)
        return {
            "bank_usdt": self.bank_usdt,
            "open_count": len(self._data["open"]),
            "closed_count": len(closed),
            "open": self._data["open"],
            "closed": list(reversed(closed[-50:])),
            "realized_pnl_usdt": round(realized, 2),
            "unrealized_pnl_usdt": round(unrealized, 2),
            "total_pnl_usdt": round(realized + unrealized, 2),
            "wins": wins,
            "losses": losses,
            "by_strategy": {k: round(v, 2) for k, v in by_strategy.items()},
        }

    def reset(self, bank_usdt: Optional[float] = None) -> dict:
        """Wipe paper book — local demo account restart."""
        if bank_usdt is not None:
            self.bank_usdt = float(bank_usdt)
        self._data = {
            "bank_usdt": self.bank_usdt,
            "open": [],
            "closed": [],
            "reset_at": self._now().isoformat(timespec="seconds"),
        }
        self.save()
        return self.summary()

