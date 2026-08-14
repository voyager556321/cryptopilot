"""News + dip / bear / rebalance / spot-grid orchestrator (paper only)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import Settings, load_config
from src.data.market import fetch_markets, create_public_exchange, fetch_portfolio_snapshot
from src.news.fetch import NewsFetcher, CoinDeskProvider, CoinTelegraphProvider
from src.news.sentiment import classify_many
from src.portfolio.paper import PaperJournal
from src.portfolio.rebalance_hints import rebalance_from_portfolio
from src.storage.news_dip_journal import NewsDipJournal
from src.strategy.news_dip import NewsDipStrategy
from src.strategy.spot_grid import SpotGridPaper
from src.utils.logging import setup_logger


class NewsDipBot:
    def __init__(self, config: Settings):
        self.config = config
        self.nd = config.news_dip
        self.st = config.strategy_test
        self.sg = config.spot_grid
        self.logger = setup_logger(
            "NewsDipBot",
            log_file=config.output_dir / "news_dip.log",
            level=20,
        )
        self.journal = NewsDipJournal(config.output_dir)
        self.strategy = NewsDipStrategy(self.nd)
        self.paper = PaperJournal(
            config.output_dir,
            bank_usdt=self.st.paper_bank_usdt,
            max_open=self.st.max_open_positions,
        )
        self.grid = SpotGridPaper(
            config.output_dir,
            symbol=self.sg.symbol,
            levels=self.sg.levels,
            range_pct=self.sg.range_pct,
            order_size_usdt=self.sg.order_size_usdt,
            fee_bps=self.sg.fee_bps,
            bank_usdt=self.sg.bank_usdt,
        )

        providers = []
        if "coindesk" in self.nd.news_sources:
            providers.append(CoinDeskProvider())
        if "cointelegraph" in self.nd.news_sources:
            providers.append(CoinTelegraphProvider())
        self.fetcher = NewsFetcher(providers) if providers else None
        self.exchange = create_public_exchange(config.exchange.name or "binance")

    def _credentials(self):
        try:
            import config as root_config
            return root_config.API_KEY or "", root_config.API_SECRET or ""
        except Exception:
            import os
            return (
                os.getenv("EXCHANGE_API_KEY") or os.getenv("BINANCE_API_KEY") or "",
                os.getenv("EXCHANGE_API_SECRET") or os.getenv("BINANCE_API_SECRET") or "",
            )

    def _run_news(self) -> bool:
        mode = self.st.mode
        return mode in ("news", "both", "all")

    def _run_rebalance(self) -> bool:
        return self.st.mode in ("rebalance", "both", "all")

    def _run_grid(self) -> bool:
        return self.sg.enabled and self.st.mode in ("grid", "all")

    def run_once(self) -> dict:
        error = None
        news_payload = []
        markets_payload = {}
        alert_payload = []
        paper_summary = self.paper.summary()
        grid_summary = self.grid.summary()
        grid_fills = []
        rebalance_view = None
        mode = self.st.mode if self.st.enabled else "news"

        try:
            markets = fetch_markets(
                self.nd,
                exchange=self.exchange,
                exchange_name=self.config.exchange.name or "binance",
            )
            markets_payload = {
                sym: {
                    "price": m.price,
                    "high": m.high,
                    "low": m.low,
                    "dip_pct": round(m.dip_pct, 4),
                    "bounce_from_low_pct": round(m.bounce_from_low_pct, 4),
                    "volume_ratio": round(m.volume_ratio, 3),
                    "change_24h_pct": None if m.change_24h_pct is None else round(m.change_24h_pct, 4),
                }
                for sym, m in markets.items()
            }
            prices = {sym: m.price for sym, m in markets.items()}

            # --- News leg ---
            if self._run_news():
                if self.fetcher is None:
                    raise RuntimeError("No news providers configured")
                news_items = self.fetcher.fetch_crypto_news(
                    max_items=30,
                    keywords=[
                        "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
                        "etf", "hack", "sec", "listing", "crypto", "sold", "sells",
                        "treasury", "holdings", "transferred",
                    ],
                )
                news_payload = classify_many(news_items, self.nd.symbols)
                signals = self.strategy.evaluate(news_items, markets)
                actionable = [s for s in signals if s.action in ("ALERT", "ALERT_SHORT", "WATCH")]
                skips = [s for s in signals if s.action == "SKIP"][:20]
                self.journal.append_signals(actionable + skips)
                alert_payload = [s.to_dict() for s in actionable]

                if self.st.enabled and self.st.auto_paper:
                    for s in actionable:
                        opened = self.paper.open_from_news_alert(s.to_dict())
                        if opened:
                            self.logger.info(
                                f"PAPER OPEN {opened['side']} {opened['symbol']} "
                                f"${opened['size_usdt']} @ {opened['entry_price']} "
                                f"[{opened['strategy']}]"
                            )

                for s in actionable:
                    self.logger.info(
                        f"{s.action} {s.side} {s.symbol} @ {s.price:.4f} "
                        f"size=${s.suggested_size_usdt:.2f} | {s.news_title}"
                    )

            # --- Rebalance leg ---
            if self._run_rebalance():
                api_key, api_secret = self._credentials()
                portfolio = fetch_portfolio_snapshot(
                    api_key, api_secret, self.config.exchange.name or "binance"
                )
                if portfolio and portfolio.get("available"):
                    rebalance_view = rebalance_from_portfolio(portfolio)
                    for h in portfolio.get("holdings") or []:
                        if h.get("symbol") and h.get("price_usdt"):
                            prices[h["symbol"]] = float(h["price_usdt"])

                    if self.st.enabled and self.st.auto_paper:
                        for hint in rebalance_view.get("actionable") or []:
                            hint = dict(hint)
                            hint["price"] = prices.get(hint["asset"])
                            if not hint["price"]:
                                continue
                            opened = self.paper.open_from_rebalance(
                                hint, fraction=self.st.rebalance_paper_fraction
                            )
                            if opened:
                                self.logger.info(
                                    f"PAPER REBALANCE {opened['side']} {opened['symbol']} "
                                    f"${opened['size_usdt']} @ {opened['entry_price']}"
                                )

            # --- Spot grid leg ---
            if self._run_grid():
                sym = self.sg.symbol
                px = prices.get(sym)
                if px:
                    self.grid.ensure_grid(px)
                    grid_fills = self.grid.on_price(px)
                    for f in grid_fills:
                        self.logger.info(
                            f"GRID {f['side'].upper()} {sym} @ {f['price']:.2f} "
                            f"qty={f['qty']} pnl={f.get('realized_pnl_usdt', 0)}"
                        )
                    grid_summary = self.grid.summary(price=px)

            paper_summary = self.paper.mark_to_market(prices)

            self.logger.info(
                f"Cycle done: mode={mode} markets={len(markets)} "
                f"alerts={len(alert_payload)} paper_open={paper_summary['open_count']} "
                f"grid_fills={len(grid_fills)} grid_pnl=${grid_summary.get('realized_pnl_usdt', 0)}"
            )
        except Exception as e:
            error = str(e)
            self.logger.error(f"run_once failed: {e}", exc_info=True)

        self.journal.update_state(
            markets=markets_payload,
            news=news_payload[:40],
            alerts=alert_payload,
            error=error,
        )
        st = self.journal.state
        st["strategy_mode"] = mode
        st["paper"] = paper_summary
        st["grid"] = grid_summary
        if rebalance_view is not None:
            st["rebalance"] = rebalance_view
        self.journal.state_path.write_text(json.dumps(st, indent=2), encoding="utf-8")

        return {
            "markets": markets_payload,
            "news": news_payload,
            "alerts": alert_payload,
            "paper": paper_summary,
            "grid": grid_summary,
            "rebalance": rebalance_view,
            "strategy_mode": mode,
            "error": error,
            "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def run_loop(self, once: bool = False):
        self.logger.info("=" * 60)
        self.logger.info("Starting STRATEGY TEST (paper, no live orders)")
        self.logger.info(f"Symbols: {self.nd.symbols}")
        self.logger.info(f"Strategy mode: {self.st.mode}")
        self.logger.info(f"Spot grid: {self.sg.symbol} levels={self.sg.levels} range={self.sg.range_pct}")
        self.logger.info(f"Poll interval: {self.nd.poll_interval_seconds}s")
        self.logger.info("=" * 60)

        while True:
            self.run_once()
            if once:
                break
            time.sleep(self.nd.poll_interval_seconds)


def run_alerts(config_path: Optional[Path] = None, once: bool = False):
    config = load_config(config_path)
    config.mode = "alerts"
    bot = NewsDipBot(config)
    bot.run_loop(once=once)
