"""Persist news-dip signals and runtime state."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.strategy.news_dip import AlertSignal


SIGNAL_COLUMNS = [
    "timestamp",
    "symbol",
    "action",
    "side",
    "strategy",
    "news_title",
    "news_url",
    "news_source",
    "sentiment",
    "confidence",
    "category",
    "price",
    "dip_pct",
    "bounce_from_low_pct",
    "volume_ratio",
    "suggested_size_usdt",
    "take_profit_pct",
    "stop_loss_pct",
    "time_stop_hours",
    "skip_reason",
    "rationale",
]


class NewsDipJournal:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.signals_path = self.output_dir / "news_dip_signals.csv"
        self.state_path = self.output_dir / "news_dip_state.json"
        self._recent: List[dict] = []
        self._state: Dict[str, Any] = {
            "last_run": None,
            "last_alerts": [],
            "markets": {},
            "news": [],
            "error": None,
        }
        self._load_recent()
        self._load_state()

    def _load_recent(self, limit: int = 200):
        if not self.signals_path.exists():
            return
        try:
            with self.signals_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            self._recent = rows[-limit:]
        except Exception:
            self._recent = []

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    def append_signals(self, signals: List[AlertSignal]):
        if not signals:
            return
        write_header = not self.signals_path.exists() or self.signals_path.stat().st_size == 0
        with self.signals_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SIGNAL_COLUMNS)
            if write_header:
                writer.writeheader()
            for signal in signals:
                row = signal.to_dict()
                writer.writerow(row)
                self._recent.append(row)
        self._recent = self._recent[-500:]

    def update_state(
        self,
        markets: Optional[Dict[str, Any]] = None,
        news: Optional[List[dict]] = None,
        alerts: Optional[List[dict]] = None,
        error: Optional[str] = None,
    ):
        self._state["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if markets is not None:
            self._state["markets"] = markets
        if news is not None:
            self._state["news"] = news
        if alerts is not None:
            self._state["last_alerts"] = alerts
        self._state["error"] = error
        self.state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def recent_signals(self, limit: int = 100, action: Optional[str] = None) -> List[dict]:
        rows = self._recent
        if action:
            rows = [r for r in rows if r.get("action") == action]
        return list(reversed(rows[-limit:]))

    @property
    def state(self) -> Dict[str, Any]:
        return self._state
