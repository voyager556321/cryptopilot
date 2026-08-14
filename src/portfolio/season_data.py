"""CoinGecko fetch + disk cache for BTC dominance and alt-season proxy."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


COINGECKO = "https://api.coingecko.com/api/v3"
STABLE_OR_WRAPPED = {
    "tether", "usd-coin", "ethena-usde", "first-digital-usd", "dai",
    "true-usd", "paypal-usd", "usds", "falcon-finance",
    "wrapped-bitcoin", "wrapped-steth", "weth", "wbeth",
    "staked-ether", "rocket-pool-eth", "coinbase-wrapped-btc",
    "binance-bridged-usdt-bnb-smart-chain", "leo-token",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_json(url: str, timeout: float = 25.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "trading-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class SeasonDataStore:
    """Cached CoinGecko snapshots for season assessment."""

    def __init__(self, output_dir: Path, *, cache_ttl_hours: float = 12.0):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.output_dir / "season_cache.json"
        self.cache_ttl_hours = float(cache_ttl_hours)
        self._cache: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.cache_path.exists():
            return {"btc_d_history": [], "snapshot": None}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            data.setdefault("btc_d_history", [])
            data.setdefault("snapshot", None)
            return data
        except Exception:
            return {"btc_d_history": [], "snapshot": None}

    def save(self) -> None:
        self.cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    def _snapshot_fresh(self) -> bool:
        snap = self._cache.get("snapshot") or {}
        fetched_at = snap.get("fetched_at")
        if not fetched_at:
            return False
        try:
            ts = datetime.fromisoformat(fetched_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_h = (_utcnow() - ts).total_seconds() / 3600.0
            return age_h < self.cache_ttl_hours
        except Exception:
            return False

    def get_snapshot(self, *, fetch: bool = True, top_n: int = 50) -> Dict[str, Any]:
        if self._snapshot_fresh() and self._cache.get("snapshot"):
            return dict(self._cache["snapshot"])
        if not fetch:
            return dict(self._cache.get("snapshot") or {})
        snap = self.fetch_live(top_n=top_n)
        self._cache["snapshot"] = snap
        self._append_btc_d(snap.get("btc_dominance"))
        self.save()
        return dict(snap)

    def _append_btc_d(self, btc_d: Optional[float]) -> None:
        if btc_d is None:
            return
        today = _utcnow().date().isoformat()
        hist: List[dict] = list(self._cache.get("btc_d_history") or [])
        if hist and hist[-1].get("date") == today:
            hist[-1] = {"date": today, "btc_dominance": float(btc_d)}
        else:
            hist.append({"date": today, "btc_dominance": float(btc_d)})
        self._cache["btc_d_history"] = hist[-120:]

    def btc_d_history(self) -> List[dict]:
        return list(self._cache.get("btc_d_history") or [])

    def fetch_live(self, *, top_n: int = 50) -> Dict[str, Any]:
        """
        CoinGecko global + markets with 90d % change.
        Alt-season proxy = % of top-N alts (excl. stables/wrapped) whose 90d
        return beats BTC's 90d return — same idea as market_chart without N calls.
        """
        global_payload = _get_json(f"{COINGECKO}/global")
        btc_d = float(
            ((global_payload.get("data") or {}).get("market_cap_percentage") or {}).get("btc")
            or 0.0
        )

        markets = _get_json(
            f"{COINGECKO}/coins/markets?"
            + urllib.parse.urlencode({
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 80,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "90d",
            })
        )

        btc_ret: Optional[float] = None
        alts: List[dict] = []
        for row in markets or []:
            cid = row.get("id") or ""
            symbol = (row.get("symbol") or "").upper()
            chg = row.get("price_change_percentage_90d_in_currency")
            if chg is None:
                continue
            ret = float(chg) / 100.0
            if cid == "bitcoin":
                btc_ret = ret
                continue
            if cid in STABLE_OR_WRAPPED:
                continue
            if symbol in {"USDT", "USDC", "FDUSD", "DAI", "TUSD", "USDE", "USD1", "USDS"}:
                continue
            alts.append({"id": cid, "symbol": symbol, "return_90d": ret})
            if len(alts) >= top_n:
                break

        beat = 0
        compared = 0
        details: List[dict] = []
        if btc_ret is not None:
            for alt in alts:
                compared += 1
                won = alt["return_90d"] > btc_ret
                if won:
                    beat += 1
                details.append({
                    "id": alt["id"],
                    "symbol": alt["symbol"],
                    "return_90d": round(alt["return_90d"], 4),
                    "beat_btc": won,
                })

        index = round(100.0 * beat / compared, 2) if compared else None
        return {
            "fetched_at": _utcnow().isoformat(timespec="seconds"),
            "btc_dominance": round(btc_d, 4),
            "btc_return_90d": None if btc_ret is None else round(btc_ret, 4),
            "alt_season_index": index,
            "alts_compared": compared,
            "alts_beat_btc": beat,
            "sample": details[:15],
            "source": "coingecko",
        }
