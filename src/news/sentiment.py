"""Rule-based news sentiment (no LLM required)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set

from src.news.fetch import NewsItem


BULL_KEYWORDS = {
    "etf", "approval", "approved", "inflow", "inflows", "adoption",
    "partnership", "partners", "institutional", "upgrade", "launch",
    "listing", "listed", "rally", "record", "all-time high", "ath",
    "bullish", "accumulation", "staking",
}

BEAR_KEYWORDS = {
    "hack", "hacked", "exploit", "breach", "stolen", "lawsuit", "sued",
    "ban", "banned", "sec charges", "fraud", "collapse", "insolvent",
    "liquidation", "liquidations", "crash", "plunge", "bearish",
    "outflow", "outflows", "delist", "delisted", "investigation",
    "arrest", "fine", "penalty", "rug", "scam",
    "sold", "sells", "selling", "sale of", "dumped", "dump",
    "transferred", "transfer to", "holdings fall", "reduces holdings",
    "unloaded", "offloaded",
}

CATEGORY_KEYWORDS = {
    "hack": {"hack", "hacked", "exploit", "breach", "stolen"},
    "etf": {"etf"},
    "listing": {"listing", "listed", "lists"},
    "regulation": {"sec", "regulation", "regulatory", "ban", "lawsuit", "cftc"},
    "partnership": {"partnership", "partners", "collaboration"},
    "unlock": {"unlock", "unlocks", "vesting"},
    "treasury_sell": {
        "sold", "sells", "selling", "sale of", "dumped", "transferred",
        "holdings fall", "reduces holdings", "unloaded", "offloaded",
        "treasury sell", "sold btc", "sold bitcoin",
    },
}

# Equity / ETF domain (IBKR stocks)
EQUITY_BULL_KEYWORDS = {
    "beat", "beats", "topped estimates", "raised guidance", "raises guidance",
    "upgrade", "upgraded", "overweight", "outperform", "buy rating",
    "record revenue", "record profit", "all-time high", "ath",
    "bullish", "surge", "soars", "jumps", "rally", "rallies",
    "partnership", "deal", "contract win", "fda approval", "approved",
    "stock split", "buyback", "dividend hike", "raised dividend",
}

EQUITY_BEAR_KEYWORDS = {
    "miss", "misses", "missed estimates", "cut guidance", "cuts guidance",
    "downgrade", "downgraded", "underweight", "underperform", "sell rating",
    "lawsuit", "sued", "probe", "investigation", "sec charges", "fraud",
    "recall", "layoffs", "cuts jobs", "warning", "plunge", "plunges",
    "crash", "crashes", "bearish", "slump", "tumbles", "sinks",
    "bankruptcy", "insolvent", "default", "fine", "penalty", "ban",
}

EQUITY_CATEGORY_KEYWORDS = {
    "earnings": {"earnings", "eps", "quarterly results", "q1", "q2", "q3", "q4"},
    "guidance": {"guidance", "outlook", "forecast"},
    "upgrade": {"upgrade", "upgraded", "overweight", "outperform"},
    "downgrade": {"downgrade", "downgraded", "underweight", "underperform"},
    "lawsuit": {"lawsuit", "sued", "litigation", "probe", "investigation"},
    "regulation": {"sec", "fda", "doj", "ftc", "ban", "antitrust"},
    "deal": {"acquisition", "merger", "takeover", "partnership", "deal"},
}

ASSET_ALIASES = {
    "BTC": {"btc", "bitcoin"},
    "ETH": {"eth", "ethereum", "ether", "etherium"},
    "SOL": {"sol", "solana"},
    "ZEC": {"zec", "zcash"},
    # IBKR holdings
    "MU": {"mu", "micron"},
    "AAPL": {"aapl", "apple"},
    "AMZN": {"amzn", "amazon"},
    "NVDA": {"nvda", "nvidia"},
    "GOOG": {"goog", "googl", "alphabet", "google"},
    "NFLX": {"nflx", "netflix"},
    "IONQ": {"ionq", "ionq inc"},
    "QBTS": {"qbts", "d-wave", "dwave"},
    "WTAI": {"wtai", "wisdomtree artificial intelligence", "ai etf"},
    "CSPX": {"cspx", "ishares core s&p", "s&p 500 ucits"},
    "CIBR": {"cibr", "cybersecurity etf", "first trust nasdaq cybersecurity"},
    "SPCX": {"spcx", "space exploration etf"},
    "QTUM": {"qtum", "defiance quantum"},
    "ROKT": {"rokt", "kensho future tech", "spdr kensho"},
    "EVX": {"evx", "vaneck environmental"},
}

HIGH_CONFIDENCE_SOURCES = {"coindesk", "cointelegraph"}
EQUITY_HIGH_CONFIDENCE_SOURCES = {"yahoo", "reuters", "cnbc", "bloomberg", "marketwatch"}


@dataclass
class SentimentResult:
    sentiment: str  # bull | bear | unclear
    confidence: str  # high | low
    category: str
    assets: List[str]
    bull_hits: int
    bear_hits: int
    rationale: str


def _text_of(item: NewsItem) -> str:
    return f"{item.title or ''} {item.summary or ''}".lower()


def detect_assets(text: str, symbols: Sequence[str], *, hints: Optional[Sequence[str]] = None) -> List[str]:
    found: List[str] = []
    for symbol in symbols:
        aliases = ASSET_ALIASES.get(symbol.upper(), {symbol.lower()})
        hit = False
        for alias in aliases:
            if len(alias) <= 3:
                if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
                    hit = True
                    break
            elif alias in text:
                hit = True
                break
        if hit:
            found.append(symbol.upper())
    # Yahoo per-ticker RSS often omits the name in the title — keep feed symbol
    if hints:
        for h in hints:
            u = str(h).upper()
            if u in {s.upper() for s in symbols} and u not in found:
                found.append(u)
    return found


def detect_category(text: str, *, domain: str = "crypto") -> str:
    cats = EQUITY_CATEGORY_KEYWORDS if domain == "equity" else CATEGORY_KEYWORDS
    for category, words in cats.items():
        if any(word in text for word in words):
            return category
    return "general"


def classify_item(
    item: NewsItem,
    symbols: Sequence[str],
    high_confidence_sources: Optional[Set[str]] = None,
    *,
    domain: str = "crypto",
) -> SentimentResult:
    text = _text_of(item)
    if domain == "equity":
        bull_kw, bear_kw = EQUITY_BULL_KEYWORDS, EQUITY_BEAR_KEYWORDS
        default_sources = EQUITY_HIGH_CONFIDENCE_SOURCES
    else:
        bull_kw, bear_kw = BULL_KEYWORDS, BEAR_KEYWORDS
        default_sources = HIGH_CONFIDENCE_SOURCES

    bull_hits = sum(1 for kw in bull_kw if kw in text)
    bear_hits = sum(1 for kw in bear_kw if kw in text)
    assets = detect_assets(text, symbols, hints=getattr(item, "symbols_hint", None) or [])
    category = detect_category(text, domain=domain)

    if bull_hits > bear_hits and bull_hits > 0:
        sentiment = "bull"
    elif bear_hits > bull_hits and bear_hits > 0:
        sentiment = "bear"
    else:
        sentiment = "unclear"

    sources = high_confidence_sources or default_sources
    source_ok = (item.source or "").lower() in sources
    confidence = "high" if source_ok and sentiment != "unclear" and (bull_hits + bear_hits) >= 1 else "low"

    rationale = (
        f"domain={domain}, sentiment={sentiment}, category={category}, "
        f"bull_hits={bull_hits}, bear_hits={bear_hits}, assets={assets or ['none']}"
    )
    return SentimentResult(
        sentiment=sentiment,
        confidence=confidence,
        category=category,
        assets=assets,
        bull_hits=bull_hits,
        bear_hits=bear_hits,
        rationale=rationale,
    )


def classify_many(
    items: Sequence[NewsItem],
    symbols: Sequence[str],
    *,
    domain: str = "crypto",
) -> List[dict]:
    results = []
    for item in items:
        s = classify_item(item, symbols, domain=domain)
        results.append({
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "published": item.published.isoformat() if item.published else None,
            "summary": item.summary,
            "sentiment": s.sentiment,
            "confidence": s.confidence,
            "category": s.category,
            "assets": s.assets,
            "rationale": s.rationale,
        })
    return results
