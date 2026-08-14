"""Yahoo Finance RSS + OHLCV helpers for equity / ETF news-dip (no API key)."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import feedparser
import numpy as np
import requests

from src.news.fetch import NewsItem
from src.news.sentiment import ASSET_ALIASES
from src.strategy.news_dip import MarketSnapshot

# London / alternate Yahoo tickers when US symbol fails
YAHOO_SYMBOL_MAP = {
    "CSPX": "CSPX.L",
}

USER_AGENT = (
    "Mozilla/5.0 (compatible; TradingBot/1.0; +https://localhost) "
    "AppleWebKit/537.36"
)


def yahoo_ticker(symbol: str) -> str:
    return YAHOO_SYMBOL_MAP.get(symbol.upper(), symbol.upper())


def keywords_for_symbols(symbols: Sequence[str]) -> List[str]:
    kws: List[str] = []
    seen = set()
    for sym in symbols:
        u = sym.upper()
        for a in ASSET_ALIASES.get(u, {u.lower()}):
            if a not in seen:
                seen.add(a)
                kws.append(a)
        if u.lower() not in seen:
            seen.add(u.lower())
            kws.append(u.lower())
    return kws


def fetch_yahoo_news_for_symbols(
    symbols: Sequence[str],
    *,
    max_per_symbol: int = 8,
    max_total: int = 40,
) -> List[NewsItem]:
    """Fetch Yahoo Finance headline RSS per ticker; dedupe by URL."""
    by_url: Dict[str, NewsItem] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for sym in symbols:
        ysym = yahoo_ticker(sym)
        url = (
            "https://feeds.finance.yahoo.com/rss/2.0/headline"
            f"?s={ysym}&region=US&lang=en-US"
        )
        try:
            resp = session.get(url, timeout=12)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"Yahoo RSS error {ysym}: {e}")
            continue

        for entry in (feed.entries or [])[:max_per_symbol]:
            link = entry.get("link") or ""
            if not link:
                continue
            published = None
            if entry.get("published_parsed"):
                try:
                    published = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                except Exception:
                    pass
            if link in by_url:
                hints = list(by_url[link].symbols_hint or [])
                if sym.upper() not in hints:
                    hints.append(sym.upper())
                    by_url[link].symbols_hint = hints
                continue
            by_url[link] = NewsItem(
                title=entry.get("title") or "",
                url=link,
                source="yahoo",
                published=published,
                summary=entry.get("summary") or "",
                symbols_hint=[sym.upper()],
            )

    items = list(by_url.values())
    items.sort(key=lambda x: x.published or datetime.min, reverse=True)
    return items[:max_total]


def _chart_to_snapshot(
    symbol: str,
    result: dict,
    *,
    lookback_hours: int = 24,
) -> Optional[MarketSnapshot]:
    try:
        chart = (result.get("chart") or {}).get("result") or []
        if not chart:
            return None
        node = chart[0]
        meta = node.get("meta") or {}
        indicators = (node.get("indicators") or {}).get("quote") or []
        if not indicators:
            return None
        q = indicators[0]
        closes = [c for c in (q.get("close") or []) if c is not None]
        highs = [c for c in (q.get("high") or []) if c is not None]
        lows = [c for c in (q.get("low") or []) if c is not None]
        volumes = [c for c in (q.get("volume") or []) if c is not None]
        if not closes:
            return None

        bars = max(2, min(len(closes), lookback_hours))
        price = float(closes[-1])
        high = float(max(highs[-bars:] if highs else closes[-bars:]))
        low = float(min(lows[-bars:] if lows else closes[-bars:]))
        dip_pct = (high - price) / high if high > 0 else 0.0
        bounce = (price - low) / low if low > 0 else 0.0

        vol_window = volumes[-bars:] if volumes else [1.0]
        vol_median = float(np.median(vol_window[:-1])) if len(vol_window) > 1 else float(vol_window[-1])
        volume_ratio = float(vol_window[-1] / vol_median) if vol_median > 0 else 1.0

        change_24h = None
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if prev:
            try:
                change_24h = (price - float(prev)) / float(prev)
            except Exception:
                pass
        if change_24h is None and len(closes) >= 24:
            change_24h = (price - float(closes[-24])) / float(closes[-24])

        return MarketSnapshot(
            symbol=symbol.upper(),
            price=price,
            high=high,
            low=low,
            dip_pct=dip_pct,
            bounce_from_low_pct=bounce,
            volume_ratio=volume_ratio,
            change_24h_pct=change_24h,
        )
    except Exception as e:
        print(f"Yahoo chart parse error {symbol}: {e}")
        return None


def fetch_yahoo_markets(
    symbols: Sequence[str],
    *,
    lookback_hours: int = 24,
    interval: str = "1h",
    range_: str = "5d",
) -> Dict[str, MarketSnapshot]:
    """Public Yahoo chart endpoint → MarketSnapshot per symbol."""
    out: Dict[str, MarketSnapshot] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for sym in symbols:
        ysym = yahoo_ticker(sym)
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
            f"?interval={interval}&range={range_}"
        )
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            snap = _chart_to_snapshot(sym, resp.json(), lookback_hours=lookback_hours)
            if snap:
                out[sym.upper()] = snap
        except Exception as e:
            print(f"Yahoo market error {ysym}: {e}")
            continue
    return out


def _ema(values: List[float], period: int) -> List[Optional[float]]:
    if period <= 0 or not values:
        return []
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def fetch_yahoo_ohlcv(
    symbol: str,
    *,
    interval: str = "1d",
    range_: str = "6mo",
) -> dict:
    """
    Daily/intraday OHLCV series from Yahoo for charting + EMA analysis.
    Returns { available, symbol, yahoo_symbol, bars:[{t,o,h,l,c,v}], ema20, ema50, error? }
    """
    sym = symbol.upper()
    ysym = yahoo_ticker(sym)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
        f"?interval={interval}&range={range_}"
    )
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {
            "available": False,
            "symbol": sym,
            "yahoo_symbol": ysym,
            "bars": [],
            "ema20": [],
            "ema50": [],
            "error": f"{type(e).__name__}: {e}",
        }

    try:
        chart = (data.get("chart") or {}).get("result") or []
        if not chart:
            return {
                "available": False,
                "symbol": sym,
                "yahoo_symbol": ysym,
                "bars": [],
                "ema20": [],
                "ema50": [],
                "error": "empty chart",
            }
        node = chart[0]
        ts = node.get("timestamp") or []
        q = ((node.get("indicators") or {}).get("quote") or [{}])[0]
        opens = q.get("open") or []
        highs = q.get("high") or []
        lows = q.get("low") or []
        closes = q.get("close") or []
        vols = q.get("volume") or []

        bars = []
        close_series: List[float] = []
        for i, t in enumerate(ts):
            c = closes[i] if i < len(closes) else None
            if c is None:
                continue
            close_series.append(float(c))
            bars.append({
                "t": datetime.utcfromtimestamp(int(t)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "o": None if i >= len(opens) or opens[i] is None else round(float(opens[i]), 4),
                "h": None if i >= len(highs) or highs[i] is None else round(float(highs[i]), 4),
                "l": None if i >= len(lows) or lows[i] is None else round(float(lows[i]), 4),
                "c": round(float(c), 4),
                "v": None if i >= len(vols) or vols[i] is None else int(vols[i]),
            })

        ema20 = _ema(close_series, 20)
        ema50 = _ema(close_series, 50)
        last = close_series[-1] if close_series else None
        e20 = ema20[-1] if ema20 else None
        e50 = ema50[-1] if ema50 else None

        return {
            "available": bool(bars),
            "symbol": sym,
            "yahoo_symbol": ysym,
            "interval": interval,
            "range": range_,
            "bars": bars,
            "ema20": [None if x is None else round(x, 4) for x in ema20],
            "ema50": [None if x is None else round(x, 4) for x in ema50],
            "last": None if last is None else round(last, 4),
            "ema20_last": None if e20 is None else round(e20, 4),
            "ema50_last": None if e50 is None else round(e50, 4),
            "dist_ema20_pct": (
                None if last is None or not e20
                else round((last - e20) / e20 * 100, 2)
            ),
            "dist_ema50_pct": (
                None if last is None or not e50
                else round((last - e50) / e50 * 100, 2)
            ),
            "error": None,
        }
    except Exception as e:
        return {
            "available": False,
            "symbol": sym,
            "yahoo_symbol": ysym,
            "bars": [],
            "ema20": [],
            "ema50": [],
            "error": f"parse: {type(e).__name__}: {e}",
        }
