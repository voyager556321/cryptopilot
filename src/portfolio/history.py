"""Append-only portfolio equity history for overview / multi-horizon PnL."""

from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


HISTORY_COLUMNS = [
    "timestamp",
    "total_usdt",
    "btc_eth_pct",
    "stable_pct",
    "alts_pct",
]

# Drawdown classification (fraction, e.g. -0.08 = −8%)
SIGNIFICANT_DD_30 = -0.08
DEEP_DD_90 = -0.15
SHALLOW_DD_30 = -0.03


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        ts = datetime.fromisoformat(value)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except Exception:
        return None


def _horizon(
    window: str,
    base: Optional[float],
    current: Optional[float],
) -> Dict[str, Any]:
    if current is None or base is None or base == 0:
        return {
            "window": window,
            "base": base,
            "current": current,
            "abs": None,
            "pct": None,
            "ready": False,
        }
    abs_v = float(current) - float(base)
    return {
        "window": window,
        "base": round(float(base), 4),
        "current": round(float(current), 4),
        "abs": round(abs_v, 2),
        "pct": round(abs_v / float(base), 4),
        "ready": True,
    }


def _points_in_window(
    series: Sequence[dict],
    *,
    now: datetime,
    days: int,
) -> List[dict]:
    since = now - timedelta(days=days)
    out: List[dict] = []
    for p in series:
        ts = _parse_ts(str(p.get("timestamp") or ""))
        if ts is None:
            continue
        if ts >= since:
            out.append({"timestamp": ts, "total_usdt": float(p["total_usdt"])})
    return out


def _first_total_since(series: Sequence[dict], since: datetime) -> Optional[float]:
    for p in series:
        ts = _parse_ts(str(p.get("timestamp") or ""))
        if ts is None:
            continue
        if ts >= since:
            return float(p["total_usdt"])
    return None


def build_pnl_context(
    series: Sequence[dict],
    current_total: Optional[float] = None,
    *,
    now: Optional[datetime] = None,
    significant_dd_30: float = SIGNIFICANT_DD_30,
    deep_dd_90: float = DEEP_DD_90,
    shallow_dd_30: float = SHALLOW_DD_30,
) -> Dict[str, Any]:
    """
    Multi-horizon PnL (1D / 7D / 30D) + peak-to-current drawdown (30d / 90d).

    ``series`` items: ``{"timestamp": iso-str, "total_usdt": float}``.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    points = []
    for p in series:
        ts = _parse_ts(str(p.get("timestamp") or ""))
        if ts is None:
            continue
        try:
            points.append({"timestamp": p["timestamp"], "total_usdt": float(p["total_usdt"])})
        except Exception:
            continue

    current = current_total
    if current is None and points:
        current = float(points[-1]["total_usdt"])

    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    base_1d = _first_total_since(points, day_ago)
    base_7d = _first_total_since(points, week_ago)
    base_30d = _first_total_since(points, month_ago)

    # Fallbacks when history is shorter than the window
    if points:
        earliest = float(points[0]["total_usdt"])
        if base_1d is None:
            base_1d = earliest
        if base_7d is None:
            base_7d = earliest
        if base_30d is None:
            base_30d = earliest

    h1d = _horizon("1d", base_1d, current)
    h7d = _horizon("7d", base_7d, current)
    h30d = _horizon("30d", base_30d, current)

    # Mark horizon not ready if we have almost no span for that window
    if len(points) < 2:
        for h in (h1d, h7d, h30d):
            h["ready"] = False

    win30 = _points_in_window(points, now=now, days=30)
    win90 = _points_in_window(points, now=now, days=90)

    def _peak_trough(window_pts: List[dict]) -> tuple[Optional[float], Optional[float]]:
        if not window_pts:
            return None, None
        vals = [p["total_usdt"] for p in window_pts]
        if current is not None:
            vals = vals + [float(current)]
        return max(vals), min(vals)

    peak30, trough30 = _peak_trough(win30)
    peak90, _trough90 = _peak_trough(win90)

    def _dd(peak: Optional[float]) -> Optional[float]:
        if current is None or peak is None or peak <= 0:
            return None
        return round(float(current) / float(peak) - 1.0, 4)

    dd30 = _dd(peak30)
    dd90 = _dd(peak90)

    bounce30: Optional[float] = None
    if current is not None and trough30 is not None and trough30 > 0:
        bounce30 = round(float(current) / float(trough30) - 1.0, 4)

    # Depth classification
    depth = "none"
    if dd90 is not None and dd90 <= deep_dd_90:
        depth = "deep"
    elif dd30 is not None and dd30 <= significant_dd_30 * 1.5:
        depth = "deep"
    elif dd30 is not None and dd30 <= significant_dd_30:
        depth = "significant"
    elif dd30 is not None and dd30 <= shallow_dd_30:
        depth = "shallow"

    in_drawdown = depth in {"significant", "deep"}

    drawdown = {
        "peak_30d": None if peak30 is None else round(float(peak30), 2),
        "peak_90d": None if peak90 is None else round(float(peak90), 2),
        "trough_30d": None if trough30 is None else round(float(trough30), 2),
        "dd_30_pct": dd30,
        "dd_90_pct": dd90,
        "bounce_from_30d_low_pct": bounce30,
        "in_drawdown": in_drawdown,
        "depth": depth,
    }

    return {
        "current_total": None if current is None else round(float(current), 2),
        "as_of": now.replace(microsecond=0).isoformat(),
        "h1d": h1d,
        "h7d": h7d,
        "h30d": h30d,
        "drawdown": drawdown,
        # Convenience aliases matching older overview fields
        "today_pnl": {"abs": h1d["abs"], "pct": h1d["pct"]},
        "pnl_24h": {"abs": h1d["abs"], "pct": h1d["pct"]},
        "pnl_7d": {"abs": h7d["abs"], "pct": h7d["pct"]},
        "pnl_30d": {"abs": h30d["abs"], "pct": h30d["pct"]},
    }


class PortfolioHistory:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "portfolio_history.csv"
        self.meta_path = self.output_dir / "portfolio_history_meta.json"
        self._min_interval_seconds = 5 * 60  # avoid spam on rapid refreshes

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _read_rows(self) -> List[dict]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception:
            return []

    def record(self, portfolio: dict, *, force: bool = False) -> bool:
        """Append a snapshot if portfolio is available. Returns True if written."""
        if not portfolio.get("available"):
            return False
        total = portfolio.get("total_usdt")
        if total is None:
            return False

        rows = self._read_rows()
        now = self._now()
        if rows and not force:
            try:
                last_ts = datetime.fromisoformat(rows[-1]["timestamp"])
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                if (now - last_ts).total_seconds() < self._min_interval_seconds:
                    return False
            except Exception:
                pass

        write_header = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow({
                "timestamp": now.replace(microsecond=0).isoformat(),
                "total_usdt": f"{float(total):.4f}",
                "btc_eth_pct": f"{float(portfolio.get('btc_eth_pct') or 0):.4f}",
                "stable_pct": f"{float(portfolio.get('stable_pct') or 0):.4f}",
                "alts_pct": f"{float(portfolio.get('alts_pct') or 0):.4f}",
            })
        return True

    def overview(self, current_total: Optional[float] = None) -> Dict[str, Any]:
        rows = self._read_rows()
        series = []
        for r in rows[-2000:]:
            try:
                series.append({
                    "timestamp": r["timestamp"],
                    "total_usdt": float(r["total_usdt"]),
                })
            except Exception:
                continue

        now = self._now()
        ctx = build_pnl_context(series, current_total, now=now)

        # Keep calendar-day baseline for UI "today" when 24h window differs
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_today = _first_total_since(series, today_start)
        if start_today is None and series:
            start_today = float(series[0]["total_usdt"])
        current = ctx["current_total"]
        if current is not None and start_today is not None and start_today != 0:
            today_abs = round(float(current) - float(start_today), 2)
            today_pct = round(today_abs / float(start_today), 4)
            today_pnl = {"abs": today_abs, "pct": today_pct}
        else:
            today_pnl = ctx["today_pnl"]

        spark = [p["total_usdt"] for p in series[-48:]]

        return {
            "points": len(series),
            "series": series[-120:],
            "sparkline": spark,
            "current_total": current,
            "today_pnl": today_pnl,
            "pnl_24h": ctx["pnl_24h"],
            "pnl_7d": ctx["pnl_7d"],
            "pnl_30d": ctx["pnl_30d"],
            "baseline_today": start_today,
            "baseline_24h": ctx["h1d"].get("base"),
            "pnl_context": ctx,
            "note": (
                "PnL is portfolio mark-to-market vs earlier snapshots in this app "
                "(not Binance cost basis / floating PnL per coin). "
                "Profit-lock uses multi-horizon context + drawdown gate."
            ),
        }

    def daily_pnl_by_date(self, current_total: Optional[float] = None) -> Dict[str, float]:
        """
        UTC calendar-day mark-to-market PnL from app snapshots:
        last equity of day − first equity of day (today: last/current − first today).
        """
        rows = self._read_rows()
        by_day: Dict[str, List[float]] = {}
        for r in rows:
            try:
                ts = datetime.fromisoformat(r["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                day = ts.date().isoformat()
                by_day.setdefault(day, []).append(float(r["total_usdt"]))
            except Exception:
                continue

        today = self._now().date().isoformat()
        out: Dict[str, float] = {}
        for day, vals in by_day.items():
            if not vals:
                continue
            end = vals[-1]
            if day == today and current_total is not None:
                end = float(current_total)
            out[day] = round(end - vals[0], 2)
        return out
