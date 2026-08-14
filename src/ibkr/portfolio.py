"""IBKR stock portfolio snapshot (file-based v1; live API later)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Theme tags for allocation / trim priority
SYMBOL_TAGS: Dict[str, str] = {
    "AAPL": "core",
    "AMZN": "core",
    "GOOG": "core",
    "NVDA": "core",
    "NFLX": "core",
    "CSPX": "core_etf",
    "MU": "semi",
    "WTAI": "ai_etf",
    "QBTS": "quantum",
    "IONQ": "quantum",
    "QTUM": "quantum",
    "SPCX": "spec_etf",
    "ROKT": "spec_etf",
    "CIBR": "theme_etf",
    "EVX": "theme_etf",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_seed_positions() -> List[dict]:
    """Seed from user IBKR screenshot (2026-08-07). Amounts / cost / MV as reported."""
    rows = [
        {"symbol": "QBTS", "name": "D-Wave Quantum", "qty": 0.35, "last": 19.93, "cost_basis": 5.12, "market_value": 6.94, "avg_price": 14.62, "daily_pnl": 0.17, "unrealized_pnl": 1.85},
        {"symbol": "CIBR", "name": "First Trust Nasdaq Cybersecurity", "qty": 0.08, "last": 98.54, "cost_basis": 5.37, "market_value": 7.94, "avg_price": 67.11, "daily_pnl": 0.23, "unrealized_pnl": 2.57},
        {"symbol": "SPCX", "name": "Space Exploration ETF", "qty": 0.07, "last": 117.34, "cost_basis": 10.96, "market_value": 8.20, "avg_price": 156.63, "daily_pnl": 0.17, "unrealized_pnl": -2.75},
        {"symbol": "MU", "name": "Micron Technology", "qty": 0.052, "last": 898.34, "cost_basis": 19.34, "market_value": 46.74, "avg_price": 371.94, "daily_pnl": 0.91, "unrealized_pnl": 27.40},
        {"symbol": "IONQ", "name": "IonQ", "qty": 0.35, "last": 40.20, "cost_basis": 10.09, "market_value": 14.12, "avg_price": 28.84, "daily_pnl": 0.16, "unrealized_pnl": 3.97},
        {"symbol": "NVDA", "name": "NVIDIA", "qty": 0.07, "last": 219.80, "cost_basis": 14.42, "market_value": 15.39, "avg_price": 205.97, "daily_pnl": 0.06, "unrealized_pnl": 0.97},
        {"symbol": "WTAI", "name": "WT Artificial Intelligence", "qty": 0.20, "last": 117.30, "cost_basis": 25.72, "market_value": 23.46, "avg_price": 128.62, "daily_pnl": 0.07, "unrealized_pnl": -2.27},
        {"symbol": "CSPX", "name": "iShares Core S&P 500", "qty": 0.02, "last": 832.02, "cost_basis": 17.99, "market_value": 16.64, "avg_price": 899.57, "daily_pnl": 0.03, "unrealized_pnl": -1.35},
        {"symbol": "GOOG", "name": "Alphabet", "qty": 0.036, "last": 356.76, "cost_basis": 10.10, "market_value": 12.87, "avg_price": 280.60, "daily_pnl": 0.00, "unrealized_pnl": 2.74},
        {"symbol": "AMZN", "name": "Amazon", "qty": 0.076, "last": 271.95, "cost_basis": 15.68, "market_value": 20.67, "avg_price": 206.32, "daily_pnl": -0.02, "unrealized_pnl": 5.00},
        {"symbol": "AAPL", "name": "Apple", "qty": 0.11, "last": 311.43, "cost_basis": 31.85, "market_value": 34.25, "avg_price": 289.52, "daily_pnl": -0.07, "unrealized_pnl": 2.45},
        {"symbol": "NFLX", "name": "Netflix", "qty": 0.20, "last": 73.44, "cost_basis": 13.75, "market_value": 14.69, "avg_price": 68.75, "daily_pnl": -0.05, "unrealized_pnl": 0.94},
        {"symbol": "ROKT", "name": "SPDR Kensho Future Tech", "qty": 0.05, "last": 118.33, "cost_basis": 5.82, "market_value": 5.92, "avg_price": 116.35, "daily_pnl": 0.00, "unrealized_pnl": 0.10},
        {"symbol": "QTUM", "name": "Defiance Quantum ETF", "qty": 0.04, "last": 149.24, "cost_basis": 5.17, "market_value": 6.02, "avg_price": 129.16, "daily_pnl": 0.05, "unrealized_pnl": 0.86},
        {"symbol": "EVX", "name": "VanEck Environmental Services", "qty": 0.13, "last": 41.38, "cost_basis": 5.23, "market_value": 5.38, "avg_price": 40.22, "daily_pnl": 0.00, "unrealized_pnl": 0.15},
    ]
    for r in rows:
        r["tag"] = SYMBOL_TAGS.get(r["symbol"], "other")
        r["change_pct"] = None
    return rows


def enrich_position(row: dict) -> dict:
    sym = str(row.get("symbol") or "").upper()
    qty = float(row.get("qty") or 0)
    last = float(row.get("last") or 0)
    avg = float(row.get("avg_price") or 0)
    mv = float(row.get("market_value") or (qty * last))
    cost = float(row.get("cost_basis") or (qty * avg if avg else 0))
    unr = row.get("unrealized_pnl")
    if unr is None and cost:
        unr = mv - cost
    daily = float(row.get("daily_pnl") or 0)
    return {
        "symbol": sym,
        "name": row.get("name") or sym,
        "qty": qty,
        "last": last,
        "avg_price": avg,
        "cost_basis": round(cost, 2),
        "market_value": round(mv, 2),
        "daily_pnl": round(daily, 2),
        "unrealized_pnl": round(float(unr or 0), 2),
        "unrealized_pnl_pct": round((float(unr or 0) / cost) * 100, 2) if cost else 0.0,
        "tag": row.get("tag") or SYMBOL_TAGS.get(sym, "other"),
    }


def build_snapshot(
    positions: List[dict],
    *,
    cash_usd: float = 0.0,
    source: str = "manual",
    synced_at: Optional[str] = None,
) -> Dict[str, Any]:
    holdings = [enrich_position(p) for p in positions if float(p.get("qty") or 0) > 0]
    invested = sum(h["market_value"] for h in holdings)
    cash = float(cash_usd or 0)
    total = invested + cash
    daily = sum(h["daily_pnl"] for h in holdings)
    unrealized = sum(h["unrealized_pnl"] for h in holdings)
    cost_total = sum(h["cost_basis"] for h in holdings)

    by_tag: Dict[str, float] = {}
    for h in holdings:
        by_tag[h["tag"]] = by_tag.get(h["tag"], 0.0) + h["market_value"]

    for h in holdings:
        h["pct"] = round(h["market_value"] / total * 100, 2) if total else 0.0

    sleeve_pct = {
        k: round(v / total * 100, 2) if total else 0.0 for k, v in by_tag.items()
    }
    cash_pct = round(cash / total * 100, 2) if total else 0.0

    return {
        "available": True,
        "broker": "ibkr",
        "source": source,
        "last_synced_at": synced_at or _utcnow(),
        "total_usd": round(total, 2),
        "invested_usd": round(invested, 2),
        "cash_usd": round(cash, 2),
        "cash_pct": cash_pct,
        "daily_pnl_usd": round(daily, 2),
        "unrealized_pnl_usd": round(unrealized, 2),
        "cost_basis_usd": round(cost_total, 2),
        "positions_count": len(holdings),
        "sleeve_pct": sleeve_pct,
        "holdings": sorted(holdings, key=lambda x: -x["market_value"]),
        "message": None,
    }


class IbkrPortfolioStore:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "ibkr_portfolio.json"

    def ensure_seed(self) -> dict:
        if self.path.exists():
            return self.load()
        snap = build_snapshot(default_seed_positions(), cash_usd=21.35, source="seed_screenshot")
        self.save(snap)
        return snap

    def load(self) -> dict:
        if not self.path.exists():
            return {
                "available": False,
                "broker": "ibkr",
                "message": "No IBKR snapshot yet.",
                "holdings": [],
                "total_usd": 0,
            }
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("available", True)
        data.setdefault("broker", "ibkr")
        return data

    def save(self, snapshot: dict) -> None:
        snapshot = dict(snapshot)
        snapshot["last_synced_at"] = snapshot.get("last_synced_at") or _utcnow()
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

    def replace_positions(self, positions: List[dict], cash_usd: float, source: str = "import") -> dict:
        snap = build_snapshot(positions, cash_usd=cash_usd, source=source)
        self.save(snap)
        return snap
