"""Public market data helpers via ccxt (no API keys required for tickers/OHLCV)."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from src.config import NewsDipConfig
from src.strategy.news_dip import MarketSnapshot


def create_public_exchange(name: str = "binance"):
    import ccxt

    exchange_cls = getattr(ccxt, name, None)
    if exchange_cls is None:
        raise ValueError(f"Unknown exchange: {name}")
    return exchange_cls({"enableRateLimit": True})


def fetch_markets(
    config: NewsDipConfig,
    exchange=None,
    exchange_name: str = "binance",
) -> Dict[str, MarketSnapshot]:
    exchange = exchange or create_public_exchange(exchange_name)
    snapshots: Dict[str, MarketSnapshot] = {}

    for symbol in config.symbols:
        pair = f"{symbol}/{config.quote}"
        try:
            ohlcv = exchange.fetch_ohlcv(
                pair,
                timeframe=config.ohlcv_timeframe,
                limit=config.ohlcv_limit,
            )
            if not ohlcv:
                continue

            closes = [c[4] for c in ohlcv]
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]

            # Use lookback window roughly matching dip_lookback_hours
            bars = max(2, min(len(ohlcv), config.dip_lookback_hours))
            window = ohlcv[-bars:]
            price = float(closes[-1])
            high = float(max(c[2] for c in window))
            low = float(min(c[3] for c in window))
            dip_pct = (high - price) / high if high > 0 else 0.0
            bounce = (price - low) / low if low > 0 else 0.0

            vol_median = float(np.median(volumes[:-1])) if len(volumes) > 1 else float(volumes[-1])
            volume_ratio = float(volumes[-1] / vol_median) if vol_median > 0 else 1.0

            change_24h = None
            try:
                ticker = exchange.fetch_ticker(pair)
                if ticker.get("percentage") is not None:
                    change_24h = float(ticker["percentage"]) / 100.0
                elif ticker.get("open") and ticker["open"]:
                    change_24h = (price - float(ticker["open"])) / float(ticker["open"])
            except Exception:
                if len(closes) >= 24:
                    change_24h = (price - float(closes[-24])) / float(closes[-24])

            snapshots[symbol] = MarketSnapshot(
                symbol=symbol,
                price=price,
                high=high,
                low=low,
                dip_pct=dip_pct,
                bounce_from_low_pct=bounce,
                volume_ratio=volume_ratio,
                change_24h_pct=change_24h,
            )
        except Exception as e:
            print(f"Market fetch error for {pair}: {e}")
            continue

    return snapshots


STABLES = ("USDT", "USDC", "FDUSD", "BUSD", "TUSD", "DAI")


def fetch_portfolio_snapshot(
    api_key: str,
    api_secret: str,
    exchange_name: str = "binance",
) -> Optional[dict]:
    """Read-only portfolio distribution (requires keys).

    Returns None if keys are missing.
    On exchange errors, returns dict with available=False and error message
    (callers that only check None should treat missing-keys None separately).
    """
    if not api_key or not api_secret:
        return None

    import ccxt

    exchange_cls = getattr(ccxt, exchange_name, ccxt.binance)
    exchange = exchange_cls({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })

    try:
        balance = exchange.fetch_balance()
        tickers = exchange.fetch_tickers()
    except Exception as e:
        return {
            "available": False,
            "error": True,
            "message": f"{exchange_name} fetch failed: {type(e).__name__}: {e}",
            "total_usdt": 0.0,
            "assets": {},
            "holdings": [],
            "btc_eth_pct": 0.0,
            "stable_pct": 0.0,
            "alts_pct": 0.0,
        }

    assets_value: Dict[str, float] = {}
    amounts: Dict[str, float] = {}
    prices: Dict[str, Optional[float]] = {}
    portfolio_value = 0.0

    for symbol, amount in (balance.get("total") or {}).items():
        if not amount or float(amount) <= 0:
            continue
        qty = float(amount)
        if symbol in STABLES:
            price = 1.0
            value = qty
        else:
            pair = f"{symbol}/USDT"
            ticker = tickers.get(pair) or {}
            last = ticker.get("last")
            if last is None:
                continue
            price = float(last)
            value = qty * price
        amounts[symbol] = qty
        prices[symbol] = price
        assets_value[symbol] = value
        portfolio_value += value

    if portfolio_value <= 0:
        return {
            "available": True,
            "total_usdt": 0.0,
            "assets": {},
            "holdings": [],
            "btc_eth_pct": 0.0,
            "stable_pct": 0.0,
            "alts_pct": 0.0,
            "message": "Exchange connected but no spot balances with USDT price",
        }

    sorted_syms = sorted(assets_value.items(), key=lambda x: -x[1])
    assets = {
        sym: {
            "quantity": amounts[sym],
            "price_usdt": prices[sym],
            "value_usdt": round(val, 2),
            "pct": round(val / portfolio_value * 100, 2),
        }
        for sym, val in sorted_syms
    }
    holdings = [
        {
            "symbol": sym,
            "quantity": amounts[sym],
            "price_usdt": prices[sym],
            "value_usdt": round(val, 2),
            "pct": round(val / portfolio_value * 100, 2),
            "asset_class": "stable" if sym in STABLES else "crypto",
        }
        for sym, val in sorted_syms
    ]

    stable = sum(assets_value.get(s, 0) for s in STABLES)
    btc_eth = sum(assets_value.get(s, 0) for s in ("BTC", "ETH"))
    alts = portfolio_value - stable - btc_eth

    return {
        "available": True,
        "total_usdt": round(portfolio_value, 2),
        "total_value_usd": round(portfolio_value, 2),
        "assets": assets,
        "holdings": holdings,
        "btc_eth_pct": round(btc_eth / portfolio_value * 100, 2),
        "stable_pct": round(stable / portfolio_value * 100, 2),
        "alts_pct": round(alts / portfolio_value * 100, 2),
        "exchange": exchange_name,
    }


_LOCK_WATCH_SYMBOLS = ["AAVE", "LINK", "FIL", "XRP", "ZEC", "SOL", "BNB"]
_LOCK_SKIP_SYMBOLS = {
    "USDT", "USDC", "FDUSD", "BUSD", "TUSD", "DAI",
    "PAXG", "XAUT", "PAX",  # gold ballast — not lock trims
    "BTC", "ETH",  # core — lock prefers alts; exclude from auto-sum
}


def _watch_symbols(symbols: Optional[List[str]] = None) -> List[str]:
    watch = symbols or list(_LOCK_WATCH_SYMBOLS)
    seen = set()
    out = []
    for s in watch:
        u = (s or "").upper()
        if not u or u in _LOCK_SKIP_SYMBOLS or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out or list(_LOCK_WATCH_SYMBOLS)


def fetch_spot_sells_usdt_range(
    api_key: str,
    api_secret: str,
    *,
    days: int = 90,
    symbols: Optional[List[str]] = None,
    exchange_name: str = "binance",
) -> dict:
    """
    Sum spot SELL fills into USDT over the last `days` UTC days, grouped by date.
    Used for profit-lock ledger today + period backfill.
    """
    if not api_key or not api_secret:
        return {
            "available": False,
            "message": "Missing API keys",
            "total_usdt": 0.0,
            "by_symbol": {},
            "by_date": {},
            "days": days,
        }

    import ccxt
    from datetime import datetime, timedelta, timezone

    exchange_cls = getattr(ccxt, exchange_name, ccxt.binance)
    exchange = exchange_cls({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })

    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    range_days = max(1, int(days))
    since_start = today_start - timedelta(days=range_days - 1)
    since_ms = int(since_start.timestamp() * 1000)

    watch = _watch_symbols(symbols)
    by_date: Dict[str, Dict[str, float]] = {}  # date -> symbol -> usdt
    fills: List[dict] = []
    errors: List[str] = []

    for sym in watch:
        pair = f"{sym}/USDT"
        cursor = since_ms
        try:
            while True:
                batch = exchange.fetch_my_trades(pair, since=cursor, limit=100) or []
                if not batch:
                    break
                for t in batch:
                    if not t.get("side") or str(t["side"]).lower() != "sell":
                        continue
                    ts = t.get("timestamp")
                    if ts is None:
                        continue
                    if int(ts) < since_ms:
                        continue
                    cost = t.get("cost")
                    if cost is None:
                        amount = float(t.get("amount") or 0)
                        price = float(t.get("price") or 0)
                        cost = amount * price
                    cost_f = float(cost or 0)
                    if cost_f <= 0:
                        continue
                    day = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).date().isoformat()
                    bucket = by_date.setdefault(day, {})
                    bucket[sym] = bucket.get(sym, 0.0) + cost_f
                    fills.append({
                        "symbol": sym,
                        "amount_usdt": round(cost_f, 2),
                        "price": t.get("price"),
                        "qty": t.get("amount"),
                        "time": t.get("datetime") or t.get("timestamp"),
                        "date": day,
                        "id": t.get("id"),
                    })
                last_ts = batch[-1].get("timestamp")
                if last_ts is None or len(batch) < 100:
                    break
                next_cursor = int(last_ts) + 1
                if next_cursor <= cursor:
                    break
                cursor = next_cursor
        except Exception as e:
            errors.append(f"{pair}: {type(e).__name__}: {e}")
            continue

    today_key = today_start.date().isoformat()
    today_by_sym = {k: round(v, 2) for k, v in sorted((by_date.get(today_key) or {}).items(), key=lambda x: -x[1])}
    today_total = round(sum(today_by_sym.values()), 2)

    by_date_out: Dict[str, dict] = {}
    for day, sym_map in by_date.items():
        total = round(sum(sym_map.values()), 2)
        by_date_out[day] = {
            "locked_usdt": total,
            "by_symbol": {k: round(v, 2) for k, v in sorted(sym_map.items(), key=lambda x: -x[1])},
        }

    grand = round(sum(v["locked_usdt"] for v in by_date_out.values()), 2)
    return {
        "available": True,
        "date": today_key,
        "days": range_days,
        "total_usdt": today_total,
        "by_symbol": today_by_sym,
        "by_date": by_date_out,
        "range_total_usdt": grand,
        "fills": fills[-80:],
        "errors": errors[:10],
        "message": None if today_total > 0 else (
            "No spot SELL fills into USDT found today (UTC). "
            + (f"API notes: {'; '.join(errors[:2])}" if errors else "Sell an alt or check keys.")
        ),
    }


def fetch_today_spot_sells_usdt(
    api_key: str,
    api_secret: str,
    symbols: Optional[List[str]] = None,
    exchange_name: str = "binance",
) -> dict:
    """Sum today's spot SELL fills into USDT (UTC day). Thin wrapper around range fetch."""
    return fetch_spot_sells_usdt_range(
        api_key,
        api_secret,
        days=1,
        symbols=symbols,
        exchange_name=exchange_name,
    )
