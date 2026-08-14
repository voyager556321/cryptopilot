"""Load history CSV and BTC bars for backtests."""

from __future__ import annotations

import csv
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class DailySnapshot:
    date: str  # YYYY-MM-DD UTC
    timestamp: str
    total_usdt: float
    btc_eth_pct: float
    stable_pct: float
    alts_pct: float


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        ts = datetime.fromisoformat(value)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except Exception:
        return None


def load_daily_snapshots(path: Path | str) -> List[DailySnapshot]:
    """Last snapshot per UTC calendar day from portfolio_history.csv."""
    path = Path(path)
    if not path.exists():
        return []
    by_day: Dict[str, DailySnapshot] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = _parse_ts(str(row.get("timestamp") or ""))
            if ts is None:
                continue
            day = ts.date().isoformat()
            try:
                snap = DailySnapshot(
                    date=day,
                    timestamp=ts.isoformat(),
                    total_usdt=float(row["total_usdt"]),
                    btc_eth_pct=float(row.get("btc_eth_pct") or 0),
                    stable_pct=float(row.get("stable_pct") or 0),
                    alts_pct=float(row.get("alts_pct") or 0),
                )
            except (TypeError, ValueError, KeyError):
                continue
            by_day[day] = snap  # last wins
    return [by_day[d] for d in sorted(by_day)]


def load_btc_bars(
    *,
    bars: Optional[Sequence[dict]] = None,
    cache_path: Optional[Path] = None,
    fetch: bool = True,
    limit: int = 200,
) -> List[dict]:
    """Daily BTC OHLC. Inject ``bars`` in tests; optionally cache under out/."""
    if bars is not None:
        return [dict(b) for b in bars]
    if cache_path and Path(cache_path).exists():
        try:
            raw = json.loads(Path(cache_path).read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                return raw
        except Exception:
            pass
    if not fetch:
        return []
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol=BTCUSDT&interval=1d&limit={limit}"
    )
    with urllib.request.urlopen(url, timeout=20) as resp:
        raw = json.loads(resp.read())
    out: List[dict] = []
    for row in raw:
        out.append({
            "ts": int(row[0]),
            "date": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date().isoformat(),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        })
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def btc_close_by_date(bars: Sequence[dict]) -> Dict[str, float]:
    return {str(b["date"]): float(b["close"]) for b in bars if b.get("date") is not None}


def daily_returns(close_by_date: Dict[str, float], dates: Sequence[str]) -> Dict[str, float]:
    """Return[date] = close[date]/close[prev] - 1 for consecutive backtest days."""
    out: Dict[str, float] = {}
    prev_close: Optional[float] = None
    for d in dates:
        c = close_by_date.get(d)
        if c is None:
            out[d] = 0.0
            continue
        if prev_close and prev_close > 0:
            out[d] = c / prev_close - 1.0
        else:
            out[d] = 0.0
        prev_close = c
    return out
