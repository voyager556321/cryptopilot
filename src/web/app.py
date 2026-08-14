"""FastAPI local dashboard for news+dip alerts + Binance portfolio (read-only)."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import load_config, Settings, CycleRebalanceConfig
from src.data.market import fetch_portfolio_snapshot, fetch_spot_sells_usdt_range
from src.news_dip_bot import NewsDipBot
from src.portfolio.history import PortfolioHistory
from src.portfolio.rebalance_hints import rebalance_from_portfolio
from src.portfolio.action_plan import build_action_plan
from src.portfolio.market_cycle import assess_market_cycle
from src.portfolio.season import assess_market_season
from src.portfolio.profit_lock_ledger import ProfitLockLedger
from src.portfolio.short_playbook import ShortWatch, build_short_playbook
from src.ibkr.portfolio import IbkrPortfolioStore
from src.ibkr.news_alerts import IbkrNewsAlerts, get_cached_or_run as ibkr_news_cached
from src.ibkr.rebalance import (
    rebalance_hints as ibkr_rebalance_hints,
    build_ibkr_action_plan,
    swing_playbook,
)
from src.ibkr.hybrid_style import hybrid_playbook
from src.ibkr.flex import flex_configured, flex_credentials_from_env, fetch_flex_snapshot, FlexError
from src.news.equity_fetch import fetch_yahoo_ohlcv

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))

_bot: Optional[NewsDipBot] = None
_config: Optional[Settings] = None
_task: Optional[asyncio.Task] = None
_portfolio_cache: Optional[dict] = None
_portfolio_synced_at: Optional[str] = None
_history: Optional[PortfolioHistory] = None
_ibkr_store: Optional[IbkrPortfolioStore] = None
_lock_ledger: Optional[ProfitLockLedger] = None
_short_watch: Optional[ShortWatch] = None
_ibkr_news: Optional[IbkrNewsAlerts] = None
_rs_closes_cache: dict = {"at": 0.0, "data": {}}


def _asset_closes_for_portfolio(portfolio: dict) -> Optional[dict]:
    """Cached daily closes for RS layer (refresh ≤ every 30 min). Failures → None."""
    import time

    from src.portfolio.relative_strength import fetch_closes_for_symbols

    holdings = portfolio.get("holdings") or []
    syms = []
    for h in holdings:
        sym = (h.get("symbol") or "").upper()
        if sym and sym not in {"USDT", "USDC", "FDUSD", "BUSD", "TUSD", "DAI", "PAXG", "XAUT"}:
            syms.append(sym)
    if not syms:
        return None
    now = time.time()
    cached = _rs_closes_cache.get("data") or {}
    if cached and now - float(_rs_closes_cache.get("at") or 0) < 1800:
        # Ensure BTC present
        if "BTC" in cached:
            return {k: cached[k] for k in set(syms) | {"BTC"} if k in cached}
    try:
        data = fetch_closes_for_symbols(syms, limit=40, include_btc=True)
        if data.get("BTC"):
            _rs_closes_cache["at"] = now
            _rs_closes_cache["data"] = data
            return data
    except Exception as exc:  # noqa: BLE001
        print(f"RS closes fetch skipped: {exc}")
    return cached or None


def _get_history() -> PortfolioHistory:
    global _history
    out = (_config.output_dir if _config else Path("out"))
    if _history is None or _history.output_dir != Path(out):
        _history = PortfolioHistory(Path(out))
    return _history


def _get_ibkr() -> IbkrPortfolioStore:
    global _ibkr_store
    out = (_config.output_dir if _config else Path("out"))
    if _ibkr_store is None or _ibkr_store.output_dir != Path(out):
        _ibkr_store = IbkrPortfolioStore(Path(out))
    return _ibkr_store


def _get_ibkr_news() -> IbkrNewsAlerts:
    global _ibkr_news
    out = (_config.output_dir if _config else Path("out"))
    if _ibkr_news is None or _ibkr_news.output_dir != Path(out):
        _ibkr_news = IbkrNewsAlerts(Path(out))
    return _ibkr_news


def _get_lock_ledger() -> ProfitLockLedger:
    global _lock_ledger
    out = (_config.output_dir if _config else Path("out"))
    if _lock_ledger is None or _lock_ledger.output_dir != Path(out):
        _lock_ledger = ProfitLockLedger(Path(out))
    return _lock_ledger


def _get_short_watch() -> ShortWatch:
    global _short_watch
    out = (_config.output_dir if _config else Path("out"))
    if _short_watch is None or _short_watch.output_dir != Path(out):
        _short_watch = ShortWatch(Path(out))
    return _short_watch


def _mark_prices(portfolio: dict) -> dict:
    prices: dict[str, float] = {}
    for h in portfolio.get("holdings") or []:
        sym = (h.get("symbol") or "").upper()
        px = h.get("price_usdt")
        if sym and px:
            prices[sym] = float(px)
    if _bot is not None:
        markets = (_bot.journal.state or {}).get("markets") or {}
        if isinstance(markets, dict):
            for sym, m in markets.items():
                if isinstance(m, dict) and m.get("price") and sym not in prices:
                    prices[str(sym).upper()] = float(m["price"])
    return prices


def _news_alerts() -> list:
    if _bot is None:
        return []
    return list((_bot.journal.state or {}).get("alerts") or [])


def _build_ibkr_overview(snapshot: dict) -> dict:
    rebalance = ibkr_rebalance_hints(snapshot) if snapshot.get("available") else {
        "policy": "Import IBKR positions to see hints.",
        "actionable": [],
        "minor": [],
        "allocation": [],
        "needs_rebalance": False,
    }
    action_plan = build_ibkr_action_plan(snapshot) if snapshot.get("available") else {
        "mode": "hold",
        "headline": "Немає IBKR знімка.",
        "actions": [],
        "checklist": [],
    }
    swing = swing_playbook(snapshot) if snapshot.get("available") else {
        "buys": [],
        "sells": [],
        "rules": [],
        "headline": "—",
    }
    # Lightweight verdicts without Yahoo (fast); EMA refresh via dedicated endpoint
    hybrid = hybrid_playbook(snapshot, with_charts=False) if snapshot.get("available") else {
        "rules": [],
        "assets": [],
        "headline": "—",
    }
    news_state = _get_ibkr_news().load()
    return {
        "available": bool(snapshot.get("available")),
        "broker": "ibkr",
        "total_usd": snapshot.get("total_usd"),
        "cash_usd": snapshot.get("cash_usd"),
        "cash_pct": snapshot.get("cash_pct"),
        "daily_pnl_usd": snapshot.get("daily_pnl_usd"),
        "unrealized_pnl_usd": snapshot.get("unrealized_pnl_usd"),
        "positions_count": snapshot.get("positions_count"),
        "last_synced_at": snapshot.get("last_synced_at"),
        "source": snapshot.get("source"),
        "sleeve_pct": snapshot.get("sleeve_pct") or {},
        "rebalance": rebalance,
        "action_plan": action_plan,
        "swing": swing,
        "hybrid": hybrid,
        "news": news_state.get("news") or [],
        "alerts": news_state.get("alerts") or [],
        "news_meta": {
            "last_run": news_state.get("last_run"),
            "error": news_state.get("error"),
            "note": news_state.get("note"),
            "stats": news_state.get("stats") or {},
            "symbols": news_state.get("symbols") or [],
        },
        "message": snapshot.get("message"),
    }


def _mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return "missing"
    if len(value) <= visible:
        return "•••• set"
    return f"••••{value[-visible:]}"


def _exchange_credentials() -> tuple[str, str]:
    try:
        import config as root_config

        api_key = root_config.API_KEY or ""
        api_secret = root_config.API_SECRET or ""
    except Exception:
        api_key = os.getenv("EXCHANGE_API_KEY") or os.getenv("BINANCE_API_KEY") or ""
        api_secret = os.getenv("EXCHANGE_API_SECRET") or os.getenv("BINANCE_API_SECRET") or ""
    return api_key, api_secret


def _exchange_name() -> str:
    return ((_config.exchange.name if _config else None) or "binance").lower()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _public_config() -> dict[str, Any]:
    api_key, api_secret = _exchange_credentials()
    nd = _config.news_dip if _config else None
    st = _config.strategy_test if _config else None
    sg = _config.spot_grid if _config else None
    openai_key = os.getenv("OPENAI_API_KEY") or ""
    return {
        "exchange": _exchange_name(),
        "sandbox": bool(_config.exchange.sandbox) if _config else False,
        "dry_run": bool(_config.exchange.dry_run) if _config else True,
        "mode": (_config.mode if _config else "alerts"),
        "api_key": _mask_secret(api_key),
        "api_secret": "•••• set" if api_secret else "missing",
        "api_keys_present": bool(api_key and api_secret),
        "openai_api_key": "•••• set" if openai_key else "missing",
        "symbols": list(nd.symbols) if nd else [],
        "quote": nd.quote if nd else "USDT",
        "bank_usdt": nd.bank_usdt if nd else None,
        "risk_per_alert_pct": nd.risk_per_alert_pct if nd else None,
        "poll_interval_seconds": nd.poll_interval_seconds if nd else None,
        "news_sources": list(nd.news_sources) if nd else [],
        "dip_min_pct": nd.dip_min_pct if nd else None,
        "dip_max_pct": nd.dip_max_pct if nd else None,
        "enable_bear_alerts": nd.enable_bear_alerts if nd else False,
        "strategy_mode": st.mode if st else "both",
        "strategy_test_enabled": st.enabled if st else False,
        "auto_paper": st.auto_paper if st else False,
        "paper_bank_usdt": st.paper_bank_usdt if st else None,
        "spot_grid": {
            "enabled": sg.enabled if sg else False,
            "symbol": sg.symbol if sg else "BTC",
            "levels": sg.levels if sg else 10,
            "range_pct": sg.range_pct if sg else 0.04,
            "order_size_usdt": sg.order_size_usdt if sg else 50,
            "bank_usdt": sg.bank_usdt if sg else 1000,
        } if sg else {},
        "connected_label": (
            f"{_exchange_name().title()} connected ({_mask_secret(api_key)})"
            if api_key and api_secret
            else f"{_exchange_name().title()} keys missing in .env"
        ),
    }


async def _load_portfolio(*, force: bool = False) -> dict:
    global _portfolio_cache, _portfolio_synced_at

    if _portfolio_cache is not None and not force:
        return {**_portfolio_cache, "last_synced_at": _portfolio_synced_at}

    api_key, api_secret = _exchange_credentials()
    if not api_key or not api_secret:
        payload = {
            "available": False,
            "message": "Set EXCHANGE_API_KEY / EXCHANGE_API_SECRET in .env for portfolio view",
            "total_usdt": 0.0,
            "assets": {},
            "holdings": [],
            "config": _public_config(),
        }
        _portfolio_cache = payload
        _portfolio_synced_at = None
        return payload

    snapshot = await asyncio.to_thread(
        fetch_portfolio_snapshot, api_key, api_secret, _exchange_name()
    )
    if snapshot is None:
        payload = {
            "available": False,
            "message": "Set EXCHANGE_API_KEY / EXCHANGE_API_SECRET in .env for portfolio view",
            "total_usdt": 0.0,
            "assets": {},
            "holdings": [],
            "config": _public_config(),
        }
    elif snapshot.get("error"):
        payload = {**snapshot, "available": False, "config": _public_config()}
    else:
        payload = {**snapshot, "available": True, "config": _public_config()}
        try:
            _get_history().record(payload, force=force)
        except Exception as e:
            print(f"Portfolio history record error: {e}")

    _portfolio_cache = payload
    _portfolio_synced_at = _utcnow_iso()
    return {**payload, "last_synced_at": _portfolio_synced_at}


def _build_overview(portfolio: dict) -> dict:
    hist = _get_history().overview(
        current_total=portfolio.get("total_usdt") if portfolio.get("available") else None
    )
    out_dir = Path(_config.output_dir) if _config else Path("out")
    cr = (_config.cycle_rebalance if _config else CycleRebalanceConfig())
    season = assess_market_season(
        cr,
        output_dir=out_dir,
        fetch=bool(cr.enabled),
    )
    if portfolio.get("available"):
        rebalance = rebalance_from_portfolio(
            portfolio,
            targets=season.get("targets"),
            thresholds_pct=cr.thresholds_pct,
            no_refill=cr.no_refill,
            min_action_usdt=float(cr.min_action_usdt),
            season=season,
        )
    else:
        rebalance = {
            "policy": "Connect exchange keys to see rebalance hints.",
            "actionable": [],
            "minor": [],
            "allocation": [],
            "needs_rebalance": False,
        }
    cycle = assess_market_cycle(
        stable_pct=portfolio.get("stable_pct") if portfolio.get("available") else None,
        fetch=True,
    )
    lock_status = _get_lock_ledger().status()
    nd = _config.news_dip if _config else None
    short_playbook = build_short_playbook(
        alerts=_news_alerts(),
        prices=_mark_prices(portfolio),
        tracked_open=_get_short_watch().current(),
        equity_usdt=portfolio.get("total_usdt") if portfolio.get("available") else None,
        tp_pct=nd.take_profit_pct if nd else 0.04,
        sl_pct=nd.stop_loss_pct if nd else 0.025,
        time_stop_hours=nd.time_stop_hours if nd else 24,
    )
    action_plan = (
        build_action_plan(
            portfolio,
            hist,
            market_cycle=cycle,
            already_locked_usdt=lock_status["locked_usdt"],
            asset_closes=_asset_closes_for_portfolio(portfolio),
        )
        if portfolio.get("available")
        else {
            "mode": "hold",
            "headline": "Connect API keys to see the lock / defense plan.",
            "actions": [],
            "checklist": [],
        }
    )
    return {
        "available": bool(portfolio.get("available")),
        "total_usdt": portfolio.get("total_usdt"),
        "btc_eth_pct": portfolio.get("btc_eth_pct"),
        "stable_pct": portfolio.get("stable_pct"),
        "alts_pct": portfolio.get("alts_pct"),
        "last_synced_at": portfolio.get("last_synced_at") or _portfolio_synced_at,
        "history": hist,
        "rebalance": rebalance,
        "action_plan": action_plan,
        "market_cycle": cycle,
        "market_season": season,
        "short_playbook": short_playbook,
        "profit_lock": {
            "date": lock_status.get("date"),
            "locked_usdt": lock_status.get("locked_usdt"),
            "periods": lock_status.get("periods"),
        },
        "message": portfolio.get("message"),
    }


async def _poll_loop():
    assert _bot is not None
    interval = _bot.nd.poll_interval_seconds
    while True:
        try:
            await asyncio.to_thread(_bot.run_once)
        except Exception as e:
            print(f"Background poll error: {e}")
        try:
            await _load_portfolio(force=True)
        except Exception as e:
            print(f"Background portfolio error: {e}")
        await asyncio.sleep(interval)


async def _warmup():
    """Background warm-up so uvicorn is not stuck on 'Waiting for application startup'."""
    try:
        await _load_portfolio(force=True)
    except Exception as e:
        print(f"Initial portfolio load error: {e}")
    try:
        assert _bot is not None
        await asyncio.to_thread(_bot.run_once)
    except Exception as e:
        print(f"Initial alert cycle error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot, _config, _task
    # Ensure .env is loaded even if config module import order differs
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass

    config_path = Path(os.getenv("NEWS_DIP_CONFIG", "configs/news_dip.yaml"))
    _config = load_config(config_path)
    _config.mode = "alerts"
    _bot = NewsDipBot(_config)
    # Do not block startup on Binance/RSS — run warm-up + poll in background
    asyncio.create_task(_warmup())
    _task = asyncio.create_task(_poll_loop())
    yield
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="News+Dip Alerts", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return TEMPLATES.TemplateResponse(request, "dashboard.html")


@app.get("/ibkr", response_class=HTMLResponse)
async def ibkr_dashboard(request: Request):
    return TEMPLATES.TemplateResponse(request, "ibkr.html")


@app.get("/landing", response_class=HTMLResponse)
async def marketing_landing(request: Request):
    """Standalone marketing page — does not touch dashboard logic."""
    return TEMPLATES.TemplateResponse(request, "landing.html")


@app.post("/api/waitlist")
async def api_waitlist(payload: dict):
    """Marketing waitlist only — isolated from portfolio APIs."""
    from src.web.waitlist import WaitlistStore

    email = (payload or {}).get("email")
    if not email or not isinstance(email, str):
        return JSONResponse({"error": "email required"}, status_code=400)
    out = Path(_config.output_dir) if _config else Path("out")
    try:
        result = WaitlistStore(out).add(email, source=str((payload or {}).get("source") or "landing"))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if result.get("duplicate"):
        return {
            "ok": True,
            "message": "You're already on the waitlist.",
            **result,
        }
    return {
        "ok": True,
        "message": "You're on the list. We'll be in touch.",
        **result,
    }


@app.get("/api/health")
async def health():
    return {"ok": True, "mode": "alerts"}


@app.get("/api/config")
async def api_config():
    return _public_config()


@app.get("/api/state")
async def api_state():
    if _bot is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    return _bot.journal.state


@app.get("/api/signals")
async def api_signals(limit: int = 50, action: Optional[str] = None):
    if _bot is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    return {"signals": _bot.journal.recent_signals(limit=limit, action=action)}


@app.get("/api/news")
async def api_news():
    if _bot is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    return {"news": _bot.journal.state.get("news", [])}


@app.get("/api/markets")
async def api_markets():
    if _bot is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    return {"markets": _bot.journal.state.get("markets", [])}


@app.get("/api/portfolio")
async def api_portfolio(refresh: bool = False):
    return await _load_portfolio(force=refresh)


@app.get("/api/overview")
async def api_overview(refresh: bool = False):
    """Wallet dynamics + threshold rebalance suggestions (no auto orders)."""
    portfolio = await _load_portfolio(force=refresh)
    return _build_overview(portfolio)


@app.get("/api/ibkr/portfolio")
async def api_ibkr_portfolio():
    store = _get_ibkr()
    return store.ensure_seed()


@app.get("/api/ibkr/overview")
async def api_ibkr_overview():
    snap = _get_ibkr().ensure_seed()
    return _build_ibkr_overview(snap)


@app.post("/api/ibkr/reload-seed")
async def api_ibkr_reload_seed():
    """Reset snapshot to the built-in screenshot seed (dev helper)."""
    from src.ibkr.portfolio import build_snapshot, default_seed_positions

    store = _get_ibkr()
    snap = build_snapshot(default_seed_positions(), cash_usd=21.35, source="seed_screenshot")
    store.save(snap)
    return {"ok": True, "overview": _build_ibkr_overview(snap)}


@app.post("/api/ibkr/import")
async def api_ibkr_import(payload: dict):
    """
    Replace IBKR snapshot.
    Body: { "cash_usd": 21.35, "positions": [ {symbol, qty, last, cost_basis, market_value, avg_price, daily_pnl, unrealized_pnl, name?} ] }
    """
    positions = (payload or {}).get("positions")
    if not isinstance(positions, list) or not positions:
        return JSONResponse({"error": "positions[] required"}, status_code=400)
    cash = float((payload or {}).get("cash_usd") or 0)
    snap = _get_ibkr().replace_positions(positions, cash_usd=cash, source="api_import")
    return {"ok": True, "overview": _build_ibkr_overview(snap)}


@app.get("/api/ibkr/flex-status")
async def api_ibkr_flex_status():
    """Whether Flex credentials are present (no secrets returned)."""
    creds = flex_credentials_from_env()
    return {
        "configured": flex_configured(),
        "has_token": bool(creds["token"]),
        "has_query_id": bool(creds["query_id"]),
        "has_account_id": bool(creds["account_id"]),
        "account_id_hint": (
            f"…{creds['account_id'][-4:]}" if creds["account_id"] and len(creds["account_id"]) >= 4
            else None
        ),
        "hint": (
            "Set IBKR_FLEX_TOKEN + IBKR_FLEX_QUERY_ID in .env "
            "(Account Management → Reports → Flex Queries → Flex Web Service)."
            if not flex_configured()
            else "Flex ready — use Sync from Flex on /ibkr."
        ),
    }


@app.post("/api/ibkr/flex-sync")
async def api_ibkr_flex_sync():
    """Pull open positions via IBKR Flex Web Service and replace local snapshot."""
    if not flex_configured():
        return JSONResponse(
            {
                "error": (
                    "IBKR Flex not configured. Add IBKR_FLEX_TOKEN and "
                    "IBKR_FLEX_QUERY_ID to .env, then restart the server."
                ),
                "configured": False,
            },
            status_code=400,
        )
    try:
        snap = await asyncio.to_thread(fetch_flex_snapshot)
        _get_ibkr().save(snap)
        return {
            "ok": True,
            "message": snap.get("message"),
            "flex": snap.get("flex"),
            "overview": _build_ibkr_overview(snap),
            "portfolio": snap,
        }
    except FlexError as e:
        return JSONResponse(
            {"error": str(e), "code": getattr(e, "code", None), "configured": True},
            status_code=400,
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}", "configured": True},
            status_code=500,
        )


@app.post("/api/ibkr/news-refresh")
async def api_ibkr_news_refresh():
    """Force Yahoo news+dip cycle for current IBKR holdings."""
    snap = _get_ibkr().ensure_seed()
    state = await asyncio.to_thread(
        lambda: ibkr_news_cached(_get_ibkr_news(), snap, force=True)
    )
    # Rebuild overview so news fields are fresh from saved state
    overview = _build_ibkr_overview(snap)
    return {
        "ok": True,
        "news": overview.get("news") or [],
        "alerts": overview.get("alerts") or [],
        "news_meta": overview.get("news_meta") or {},
        "overview": overview,
    }


@app.post("/api/ibkr/hybrid-refresh")
async def api_ibkr_hybrid_refresh():
    """Refresh hybrid swing/positional EMA analysis (Yahoo daily)."""
    snap = _get_ibkr().ensure_seed()
    hybrid = await asyncio.to_thread(lambda: hybrid_playbook(snap, with_charts=True))
    return {"ok": True, "hybrid": hybrid}


@app.get("/api/ibkr/chart/{symbol}")
async def api_ibkr_chart(symbol: str, range: str = "6mo", interval: str = "1d"):
    """Yahoo OHLCV + EMA20/50 for IBKR chart panel."""
    allowed_range = {"1mo", "3mo", "6mo", "1y", "5d", "1d"}
    allowed_interval = {"1d", "1h", "15m", "5m"}
    if range not in allowed_range:
        range = "6mo"
    if interval not in allowed_interval:
        interval = "1d"
    data = await asyncio.to_thread(
        fetch_yahoo_ohlcv, symbol.upper(), interval=interval, range_=range
    )
    if not data.get("available"):
        return JSONResponse(data, status_code=200)
    return data


@app.get("/api/profit-lock")
async def api_profit_lock_status():
    return _get_lock_ledger().status()


@app.post("/api/profit-lock")
async def api_profit_lock_record(payload: dict):
    """Record a manual profit-lock trim so advice stops repeating the full amount."""
    try:
        amount = float((payload or {}).get("amount_usdt") or 0)
        status = _get_lock_ledger().record(
            amount,
            note=str((payload or {}).get("note") or ""),
            symbol=str((payload or {}).get("symbol") or ""),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "ledger": status}


@app.post("/api/profit-lock/reset")
async def api_profit_lock_reset():
    return {"ok": True, "ledger": _get_lock_ledger().reset_today()}


@app.post("/api/profit-lock/detect")
async def api_profit_lock_detect():
    """Pull spot SELLs, keep only take-profit days (green portfolio PnL), sync ledger."""
    api_key, api_secret = _exchange_credentials()
    if not api_key or not api_secret:
        return JSONResponse({"error": "Exchange API keys missing"}, status_code=400)
    portfolio = await _load_portfolio(force=False)
    symbols = None
    if portfolio.get("available"):
        from src.data.market import _LOCK_WATCH_SYMBOLS, _LOCK_SKIP_SYMBOLS

        held = []
        for h in portfolio.get("holdings") or []:
            sym = (h.get("symbol") or "").upper()
            if sym and sym not in _LOCK_SKIP_SYMBOLS:
                held.append(sym)
        for sym in portfolio.get("assets") or {}:
            u = str(sym).upper()
            if u and u not in _LOCK_SKIP_SYMBOLS:
                held.append(u)
        symbols = list(dict.fromkeys([*_LOCK_WATCH_SYMBOLS, *held]))
    detected = await asyncio.to_thread(
        fetch_spot_sells_usdt_range,
        api_key,
        api_secret,
        days=90,
        symbols=symbols,
        exchange_name=_exchange_name(),
    )
    lock_trigger = 10.0
    daily_pnl = _get_history().daily_pnl_by_date(
        current_total=portfolio.get("total_usdt") if portfolio.get("available") else None
    )
    # Live today overlay from overview logic
    hist = _get_history().overview(
        current_total=portfolio.get("total_usdt") if portfolio.get("available") else None
    )
    today_abs = (hist.get("today_pnl") or {}).get("abs")
    today_key = detected.get("date") or _get_lock_ledger()._today()
    if today_abs is not None:
        daily_pnl[today_key] = float(today_abs)

    ledger = _get_lock_ledger()
    skipped = []
    tp_days: dict = {}
    if detected.get("available"):
        by_date = dict(detected.get("by_date") or {})
        if today_key and today_key not in by_date:
            by_date[today_key] = {
                "locked_usdt": float(detected.get("total_usdt") or 0),
                "by_symbol": detected.get("by_symbol") or {},
            }
        for day, payload in by_date.items():
            sells = float((payload or {}).get("locked_usdt") or 0)
            if sells <= 0:
                continue
            pnl = daily_pnl.get(day)
            if pnl is None:
                skipped.append({"date": day, "sells_usdt": sells, "reason": "no_portfolio_history"})
                continue
            if float(pnl) < lock_trigger:
                skipped.append({
                    "date": day,
                    "sells_usdt": sells,
                    "day_pnl_usdt": pnl,
                    "reason": "not_green_enough",
                })
                continue
            tp_days[day] = {
                **payload,
                "day_pnl_usdt": pnl,
            }
        status = ledger.replace_take_profit_days(tp_days)
    else:
        status = ledger.status()
    return {
        "ok": True,
        "detected": detected,
        "ledger": status,
        "take_profit_filter": {
            "lock_trigger_usdt": lock_trigger,
            "kept_days": sorted(tp_days.keys()),
            "skipped": skipped,
        },
    }


@app.get("/api/rebalance")
async def api_rebalance():
    portfolio = await _load_portfolio(force=False)
    if not portfolio.get("available"):
        return {
            "needs_rebalance": False,
            "actionable": [],
            "minor": [],
            "message": portfolio.get("message") or "Portfolio unavailable",
        }
    out_dir = Path(_config.output_dir) if _config else Path("out")
    cr = (_config.cycle_rebalance if _config else CycleRebalanceConfig())
    season = assess_market_season(cr, output_dir=out_dir, fetch=bool(cr.enabled))
    return rebalance_from_portfolio(
        portfolio,
        targets=season.get("targets"),
        thresholds_pct=cr.thresholds_pct,
        no_refill=cr.no_refill,
        min_action_usdt=float(cr.min_action_usdt),
        season=season,
    )


@app.get("/api/paper")
async def api_paper():
    if _bot is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    return _bot.paper.summary()


@app.post("/api/short-watch")
async def api_short_watch_open(payload: dict):
    """Track a short the user opened (futures/margin). Advice only — no Binance order."""
    nd = _config.news_dip if _config else None
    body = dict(payload or {})
    if nd:
        body.setdefault("take_profit_pct", nd.take_profit_pct)
        body.setdefault("stop_loss_pct", nd.stop_loss_pct)
        body.setdefault("time_stop_hours", nd.time_stop_hours)
    try:
        pos = _get_short_watch().open_one(body)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "position": pos}


@app.post("/api/short-watch/close")
async def api_short_watch_close(payload: dict):
    pos_id = (payload or {}).get("id")
    if not pos_id:
        current = _get_short_watch().current()
        pos_id = current.get("id") if current else None
    if not pos_id:
        return JSONResponse({"error": "no tracked short"}, status_code=400)
    try:
        closed = _get_short_watch().close(str(pos_id), reason=(payload or {}).get("reason") or "manual")
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "closed": closed}


@app.get("/api/grid")
async def api_grid():
    if _bot is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    markets = (_bot.journal.state or {}).get("markets") or {}
    sym = _bot.sg.symbol
    px = (markets.get(sym) or {}).get("price")
    return _bot.grid.summary(price=px)


@app.post("/api/grid/reset")
async def api_grid_reset():
    if _bot is None or _config is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    summary = _bot.grid.reset(bank_usdt=_config.spot_grid.bank_usdt)
    return {"ok": True, "message": "Spot grid reset", "grid": summary}


@app.post("/api/paper/reset")
async def api_paper_reset():
    """Reset local demo/paper account."""
    if _bot is None or _config is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    bank = _config.strategy_test.paper_bank_usdt
    summary = _bot.paper.reset(bank_usdt=bank)
    return {"ok": True, "message": f"Demo paper account reset to ${bank:.0f}", "paper": summary}


@app.post("/api/strategy-mode")
async def api_strategy_mode(payload: dict):
    """Switch paper-test mode: news | rebalance | grid | both | all."""
    if _bot is None or _config is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    mode = (payload or {}).get("mode")
    if mode not in ("news", "rebalance", "grid", "both", "all"):
        return JSONResponse(
            {"error": "mode must be news|rebalance|grid|both|all"},
            status_code=400,
        )
    _config.strategy_test.mode = mode
    _bot.st.mode = mode
    return {"ok": True, "strategy_mode": mode}


@app.get("/api/accounts")
async def api_accounts():
    """Lightweight account list derived from .env (no secrets)."""
    cfg = _public_config()
    api_key, api_secret = _exchange_credentials()
    if not (api_key and api_secret):
        return []
    return [
        {
            "id": 1,
            "name": f"{cfg['exchange'].title()} (.env)",
            "source": cfg["exchange"],
            "enabled": True,
            "last_synced_at": _portfolio_synced_at,
            "api_key": cfg["api_key"],
            "status": "connected",
        }
    ]


@app.post("/api/sync")
async def api_sync():
    """Refresh Binance portfolio + run one news-dip alert cycle."""
    results = []
    portfolio = await _load_portfolio(force=True)
    if portfolio.get("available"):
        holdings = portfolio.get("holdings") or []
        results.append(
            {
                "source": _exchange_name(),
                "account_id": 1,
                "status": "success",
                "message": f"Portfolio ${portfolio.get('total_usdt', 0):,.2f}",
                "assets_count": len(holdings) or len(portfolio.get("assets") or {}),
            }
        )
    else:
        results.append(
            {
                "source": _exchange_name(),
                "account_id": 1 if _public_config()["api_keys_present"] else None,
                "status": "error",
                "message": portfolio.get("message") or "Portfolio unavailable",
                "assets_count": 0,
            }
        )

    if _bot is not None:
        try:
            run = await asyncio.to_thread(_bot.run_once)
            results.append(
                {
                    "source": "news_dip",
                    "account_id": None,
                    "status": "success",
                    "message": f"Alert cycle ok · markets={len((run or {}).get('markets') or {})}",
                    "assets_count": 0,
                }
            )
        except Exception as e:
            results.append(
                {
                    "source": "news_dip",
                    "account_id": None,
                    "status": "error",
                    "message": str(e),
                    "assets_count": 0,
                }
            )

    return results


@app.post("/api/run-once")
async def api_run_once():
    if _bot is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    result = await asyncio.to_thread(_bot.run_once)
    return result


def main():
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
