"""Track locked (realized-to-USDT) amounts for crypto profit-lock — today + history."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProfitLockLedger:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "profit_lock_ledger.json"

    def _today(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _empty(self) -> dict:
        today = self._today()
        return {
            "date": today,
            "locked_usdt": 0.0,
            "entries": [],
            "days": {
                today: {"locked_usdt": 0.0, "entries": []},
            },
        }

    def _normalize(self, raw: dict) -> dict:
        """Migrate legacy single-day files and sync today alias from days."""
        today = self._today()
        days: Dict[str, Any] = dict(raw.get("days") or {})

        # Migrate legacy: only top-level date/locked/entries
        legacy_date = raw.get("date")
        if legacy_date and legacy_date not in days:
            days[legacy_date] = {
                "locked_usdt": round(float(raw.get("locked_usdt") or 0), 2),
                "entries": list(raw.get("entries") or []),
                "source": raw.get("source"),
            }

        if today not in days:
            days[today] = {"locked_usdt": 0.0, "entries": []}

        today_row = days[today]
        return {
            "date": today,
            "locked_usdt": round(float(today_row.get("locked_usdt") or 0), 2),
            "entries": list(today_row.get("entries") or []),
            "source": today_row.get("source"),
            "days": days,
        }

    def _load(self) -> dict:
        if not self.path.exists():
            return self._empty()
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return self._empty()
        if not isinstance(raw, dict):
            return self._empty()
        data = self._normalize(raw)
        # Persist migration so periods survive without another Detect
        if "days" not in raw:
            self._save(data)
        return data

    def _save(self, data: dict) -> None:
        data = self._normalize(data)
        # Keep only last ~120 days to bound file size
        days = data.get("days") or {}
        if len(days) > 120:
            keep_from = (datetime.now(timezone.utc).date() - timedelta(days=120)).isoformat()
            days = {k: v for k, v in days.items() if k >= keep_from}
            data["days"] = days
            data = self._normalize(data)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _sync_today_alias(self, data: dict) -> dict:
        today = self._today()
        days = data.setdefault("days", {})
        row = days.setdefault(today, {"locked_usdt": 0.0, "entries": [], "kind": "take_profit"})
        data["date"] = today
        if (row.get("kind") or "") == "take_profit":
            data["locked_usdt"] = round(float(row.get("locked_usdt") or 0), 2)
            data["entries"] = list(row.get("entries") or [])
            if row.get("source"):
                data["source"] = row["source"]
        else:
            data["locked_usdt"] = 0.0
            data["entries"] = []
        return data

    def status(self) -> Dict[str, Any]:
        data = self._load()
        out = {
            "date": data["date"],
            "locked_usdt": round(float(data.get("locked_usdt") or 0), 2),
            "entries": list(data.get("entries") or []),
            "periods": self.periods(data),
        }
        if data.get("source"):
            out["source"] = data["source"]
        return out

    def periods(self, data: Optional[dict] = None) -> Dict[str, Any]:
        data = data or self._load()
        days: Dict[str, Any] = data.get("days") or {}
        today = date.fromisoformat(self._today())

        def _is_tp(row: Optional[dict]) -> bool:
            if not row:
                return False
            return (row.get("kind") or "") == "take_profit"

        def _sum_since(n_days: int) -> Dict[str, Any]:
            start = (today - timedelta(days=n_days - 1)).isoformat()
            total = 0.0
            count = 0
            for d, row in days.items():
                if d < start or not _is_tp(row):
                    continue
                amt = float((row or {}).get("locked_usdt") or 0)
                if amt != 0 or (row or {}).get("entries"):
                    count += 1
                total += amt
            return {
                "locked_usdt": round(total, 2),
                "days_with_data": count,
                "from": start,
                "to": today.isoformat(),
            }

        day_key = today.isoformat()
        day_row = days.get(day_key) or {}
        day_amt = round(float(day_row.get("locked_usdt") or 0), 2) if _is_tp(day_row) else 0.0
        return {
            "day": {
                "locked_usdt": day_amt,
                "days_with_data": 1 if day_amt else 0,
                "from": day_key,
                "to": day_key,
            },
            "week": _sum_since(7),
            "month": _sum_since(30),
            "quarter": _sum_since(90),
            "note": (
                "Take-profit only: alt sells on green portfolio days "
                f"(daily PnL ≥ lock trigger). Defense / unknown days excluded."
            ),
        }

    def record(self, amount_usdt: float, *, note: str = "", symbol: str = "") -> dict:
        amount = abs(float(amount_usdt))
        if amount <= 0:
            raise ValueError("amount_usdt must be > 0")
        data = self._load()
        today = self._today()
        days = data.setdefault("days", {})
        row = days.setdefault(today, {"locked_usdt": 0.0, "entries": [], "kind": "take_profit"})
        row["kind"] = "take_profit"
        row["locked_usdt"] = round(float(row.get("locked_usdt") or 0) + amount, 2)
        entries: List[dict] = list(row.get("entries") or [])
        entries.append({
            "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "amount_usdt": round(amount, 2),
            "symbol": (symbol or "").upper() or None,
            "note": note or "manual_take_profit",
        })
        row["entries"] = entries[-40:]
        days[today] = row
        data["days"] = days
        data = self._sync_today_alias(data)
        self._save(data)
        return self.status()

    def reset_today(self) -> dict:
        data = self._load()
        today = self._today()
        days = data.setdefault("days", {})
        days[today] = {"locked_usdt": 0.0, "entries": [], "kind": "take_profit"}
        data["days"] = days
        data = self._sync_today_alias(data)
        self._save(data)
        return self.status()

    def sync_from_exchange(self, detected: dict, *, kind: str = "take_profit", day_pnl: Optional[float] = None) -> dict:
        """
        Replace today's locked amount with sum of spot SELLs (UTC day).
        Preserves other days. Used when today already classified as take-profit.
        """
        if not detected.get("available"):
            return self.status()
        total = float(detected.get("total_usdt") or 0)
        by_sym = detected.get("by_symbol") or {}
        day = detected.get("date") or self._today()
        data = self._load()
        days = data.setdefault("days", {})
        row = {
            "locked_usdt": round(total, 2),
            "entries": [
                {
                    "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "amount_usdt": round(float(amt), 2),
                    "symbol": sym,
                    "note": "binance_spot_sell",
                }
                for sym, amt in by_sym.items()
            ],
            "source": "binance",
            "kind": kind,
        }
        if day_pnl is not None:
            row["day_pnl_usdt"] = round(float(day_pnl), 2)
        days[day] = row
        data["days"] = days
        data = self._sync_today_alias(data)
        self._save(data)
        return self.status()

    def replace_take_profit_days(self, by_date: Dict[str, dict]) -> dict:
        """
        Rebuild archive with take-profit days only (green-day alt sells).
        Drops previous all-sells / defense days from the ledger.
        by_date: { date: { locked_usdt, by_symbol?, day_pnl_usdt? } }
        """
        data = self._load()
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        new_days: Dict[str, Any] = {}
        for day, payload in (by_date or {}).items():
            if not day:
                continue
            total = round(float((payload or {}).get("locked_usdt") or 0), 2)
            if total <= 0:
                continue
            by_sym = (payload or {}).get("by_symbol") or {}
            entries = [
                {
                    "at": now_iso,
                    "amount_usdt": round(float(amt), 2),
                    "symbol": sym,
                    "note": "binance_take_profit",
                }
                for sym, amt in by_sym.items()
            ]
            if not entries:
                entries = [{
                    "at": now_iso,
                    "amount_usdt": total,
                    "symbol": None,
                    "note": "binance_take_profit",
                }]
            row: Dict[str, Any] = {
                "locked_usdt": total,
                "entries": entries,
                "source": "binance",
                "kind": "take_profit",
            }
            if (payload or {}).get("day_pnl_usdt") is not None:
                row["day_pnl_usdt"] = round(float(payload["day_pnl_usdt"]), 2)
            new_days[day] = row

        today = self._today()
        if today not in new_days:
            new_days[today] = {"locked_usdt": 0.0, "entries": [], "kind": "take_profit"}

        data["days"] = new_days
        data = self._sync_today_alias(data)
        self._save(data)
        return self.status()

    def merge_daily_totals(self, by_date: Dict[str, dict]) -> dict:
        """Deprecated path — prefer replace_take_profit_days for Detect."""
        return self.replace_take_profit_days(by_date)