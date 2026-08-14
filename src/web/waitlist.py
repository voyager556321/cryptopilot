"""Isolated waitlist storage for the marketing landing page."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class WaitlistStore:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "waitlist.json"
        self._data: Dict[str, Any] = {"entries": []}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("entries"), list):
                self._data = raw
            elif isinstance(raw, list):
                self._data = {"entries": raw}
        except Exception:
            pass

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def add(self, email: str, *, source: str = "landing") -> Dict[str, Any]:
        email_n = email.strip().lower()
        if not _EMAIL_RE.match(email_n):
            raise ValueError("Invalid email address")
        entries: List[dict] = list(self._data.get("entries") or [])
        for row in entries:
            if (row.get("email") or "").lower() == email_n:
                return {"ok": True, "duplicate": True, "email": email_n}
        entries.append({
            "email": email_n,
            "source": source or "landing",
            "created_at": _utcnow(),
        })
        self._data["entries"] = entries
        self.save()
        return {"ok": True, "duplicate": False, "email": email_n}
