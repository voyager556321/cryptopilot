"""Paper spot-grid strategy (range trading, no live orders)."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GridLevel:
    price: float
    side: str  # buy below mid, sell above mid (initial placement)
    filled: bool = False
    fill_price: Optional[float] = None
    # After a buy fill, we place a sell one step up; after sell, buy one step down
    paired: bool = False


class SpotGridPaper:
    """
    Classic spot grid on paper:
    - Build N levels across [low, high]
    - Price drops through a buy level → buy size_usdt
    - Price rises through a sell level → sell inventory (or sell size)
    - Realized PnL counted on round-trips (buy then sell above)
    """

    def __init__(
        self,
        output_dir: Path,
        symbol: str = "BTC",
        levels: int = 10,
        range_pct: float = 0.04,
        order_size_usdt: float = 50.0,
        fee_bps: float = 10.0,
        bank_usdt: float = 1000.0,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "spot_grid_state.json"
        self.symbol = symbol
        self.levels_n = max(4, int(levels))
        self.range_pct = float(range_pct)
        self.order_size_usdt = float(order_size_usdt)
        self.fee_rate = float(fee_bps) / 10000.0
        self.bank_usdt = float(bank_usdt)

        self._state: Dict[str, Any] = {
            "symbol": symbol,
            "mid": None,
            "low": None,
            "high": None,
            "step": None,
            "levels": [],
            "cash_usdt": bank_usdt,
            "inventory": 0.0,  # base asset qty
            "avg_entry": 0.0,
            "realized_pnl_usdt": 0.0,
            "fees_paid": 0.0,
            "fills": [],
            "created_at": None,
            "updated_at": None,
            "status": "idle",
        }
        self._load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _load(self):
        if not self.path.exists():
            return
        try:
            self._state = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            pass

    def save(self):
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def reset(self, bank_usdt: Optional[float] = None):
        if bank_usdt is not None:
            self.bank_usdt = float(bank_usdt)
        self._state = {
            "symbol": self.symbol,
            "mid": None,
            "low": None,
            "high": None,
            "step": None,
            "levels": [],
            "cash_usdt": self.bank_usdt,
            "inventory": 0.0,
            "avg_entry": 0.0,
            "realized_pnl_usdt": 0.0,
            "fees_paid": 0.0,
            "fills": [],
            "created_at": None,
            "updated_at": self._now(),
            "status": "idle",
        }
        self.save()
        return self.summary()

    def ensure_grid(self, price: float, force: bool = False) -> dict:
        """Create grid around price if missing or price left the band."""
        if price <= 0:
            return self.summary()

        low = self._state.get("low")
        high = self._state.get("high")
        need_new = force or not self._state.get("levels")
        if low and high and (price < low or price > high):
            need_new = True
            # Realize nothing on recenter; keep inventory/cash, rebuild levels
        if not need_new:
            return self.summary()

        half = self.range_pct / 2.0
        mid = float(price)
        band_low = mid * (1 - half)
        band_high = mid * (1 + half)
        n = self.levels_n
        step = (band_high - band_low) / (n - 1)

        levels = []
        for i in range(n):
            lvl_price = band_low + i * step
            # below mid → buy waiting; at/above mid → sell waiting (need inventory later)
            side = "buy" if lvl_price < mid else "sell"
            levels.append({
                "price": round(lvl_price, 4),
                "side": side,
                "filled": False,
                "active": True,
            })

        self._state.update({
            "symbol": self.symbol,
            "mid": round(mid, 4),
            "low": round(band_low, 4),
            "high": round(band_high, 4),
            "step": round(step, 4),
            "levels": levels,
            "created_at": self._state.get("created_at") or self._now(),
            "updated_at": self._now(),
            "status": "active",
            "range_pct": self.range_pct,
            "order_size_usdt": self.order_size_usdt,
            "levels_n": n,
        })
        if self._state.get("cash_usdt") is None:
            self._state["cash_usdt"] = self.bank_usdt
        self.save()
        return self.summary()

    def on_price(self, price: float) -> List[dict]:
        """Process price tick; return new fills."""
        if price <= 0:
            return []

        if not self._state.get("levels"):
            self.ensure_grid(price)

        fills: List[dict] = []
        levels = self._state.get("levels") or []
        prev = self._state.get("last_price")
        self._state["last_price"] = price

        for lvl in levels:
            if not lvl.get("active", True):
                continue
            lvl_price = float(lvl["price"])
            side = lvl["side"]

            # Require a real cross from the previous tick (skip first tick bootstrap)
            if prev is None:
                continue

            crossed_buy = side == "buy" and prev > lvl_price >= price
            crossed_sell = side == "sell" and prev < lvl_price <= price

            if crossed_buy:
                fill = self._fill_buy(lvl_price)
                if fill:
                    fills.append(fill)
                    # Flip this level to a sell one step up
                    lvl["side"] = "sell"
                    lvl["price"] = round(lvl_price + float(self._state["step"]), 4)
            elif crossed_sell:
                fill = self._fill_sell(lvl_price)
                if fill:
                    fills.append(fill)
                    lvl["side"] = "buy"
                    lvl["price"] = round(lvl_price - float(self._state["step"]), 4)

        if fills:
            self._state["updated_at"] = self._now()
            existing = self._state.get("fills") or []
            existing.extend(fills)
            self._state["fills"] = existing[-200:]

        # Recenter only after processing fills, if price left the band
        low = self._state.get("low")
        high = self._state.get("high")
        if low is not None and high is not None and (price < low or price > high):
            self.ensure_grid(price, force=True)

        self._state["updated_at"] = self._now()
        self.save()
        return fills

    def _fill_buy(self, price: float) -> Optional[dict]:
        size = self.order_size_usdt
        fee = size * self.fee_rate
        cost = size + fee
        cash = float(self._state.get("cash_usdt") or 0)
        if cash < cost:
            return None
        qty = size / price
        inv = float(self._state.get("inventory") or 0)
        avg = float(self._state.get("avg_entry") or 0)
        new_inv = inv + qty
        self._state["avg_entry"] = ((avg * inv) + size) / new_inv if new_inv > 0 else 0.0
        self._state["inventory"] = new_inv
        self._state["cash_usdt"] = cash - cost
        self._state["fees_paid"] = float(self._state.get("fees_paid") or 0) + fee
        return {
            "timestamp": self._now(),
            "side": "buy",
            "price": price,
            "qty": round(qty, 8),
            "usdt": size,
            "fee": round(fee, 4),
            "realized_pnl_usdt": 0.0,
        }

    def _fill_sell(self, price: float) -> Optional[dict]:
        inv = float(self._state.get("inventory") or 0)
        if inv <= 0:
            return None
        size = self.order_size_usdt
        qty = min(inv, size / price)
        if qty <= 0:
            return None
        proceeds = qty * price
        fee = proceeds * self.fee_rate
        avg = float(self._state.get("avg_entry") or 0)
        cost_basis = qty * avg
        realized = proceeds - fee - cost_basis
        self._state["inventory"] = inv - qty
        if self._state["inventory"] <= 1e-12:
            self._state["inventory"] = 0.0
            self._state["avg_entry"] = 0.0
        self._state["cash_usdt"] = float(self._state.get("cash_usdt") or 0) + proceeds - fee
        self._state["realized_pnl_usdt"] = float(self._state.get("realized_pnl_usdt") or 0) + realized
        self._state["fees_paid"] = float(self._state.get("fees_paid") or 0) + fee
        return {
            "timestamp": self._now(),
            "side": "sell",
            "price": price,
            "qty": round(qty, 8),
            "usdt": round(proceeds, 4),
            "fee": round(fee, 4),
            "realized_pnl_usdt": round(realized, 4),
        }

    def mark_equity(self, price: float) -> float:
        cash = float(self._state.get("cash_usdt") or 0)
        inv = float(self._state.get("inventory") or 0)
        return cash + inv * price

    def summary(self, price: Optional[float] = None) -> dict:
        px = price or self._state.get("last_price")
        equity = self.mark_equity(float(px)) if px else float(self._state.get("cash_usdt") or 0)
        unrealized = 0.0
        if px and float(self._state.get("inventory") or 0) > 0:
            inv = float(self._state["inventory"])
            avg = float(self._state.get("avg_entry") or 0)
            unrealized = inv * (float(px) - avg)
        return {
            "status": self._state.get("status", "idle"),
            "symbol": self._state.get("symbol", self.symbol),
            "mid": self._state.get("mid"),
            "low": self._state.get("low"),
            "high": self._state.get("high"),
            "step": self._state.get("step"),
            "range_pct": self._state.get("range_pct", self.range_pct),
            "levels_n": self._state.get("levels_n", self.levels_n),
            "order_size_usdt": self._state.get("order_size_usdt", self.order_size_usdt),
            "levels": self._state.get("levels") or [],
            "cash_usdt": round(float(self._state.get("cash_usdt") or 0), 2),
            "inventory": float(self._state.get("inventory") or 0),
            "avg_entry": float(self._state.get("avg_entry") or 0),
            "realized_pnl_usdt": round(float(self._state.get("realized_pnl_usdt") or 0), 2),
            "unrealized_pnl_usdt": round(unrealized, 2),
            "fees_paid": round(float(self._state.get("fees_paid") or 0), 2),
            "equity_usdt": round(equity, 2),
            "fills": list(reversed((self._state.get("fills") or [])[-40:])),
            "fill_count": len(self._state.get("fills") or []),
            "last_price": self._state.get("last_price"),
            "updated_at": self._state.get("updated_at"),
        }
