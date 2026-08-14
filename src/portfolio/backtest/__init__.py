"""Backtest the production ``build_action_plan`` on historical sleeve snapshots.

Does **not** reimplement strategy rules. Each day:

  historical sleeves + PnL series + BTC cycle bars
        → build_action_plan()   # same function as /api/overview
        → journal row + optional simulated lock execution
        → portfolio / baseline evolution

Limitation (honest): ``portfolio_history.csv`` has sleeve percents only
(no per-coin bags). Holdings are reconstructed as BTC/ETH/alts buckets so
trim ordering still runs; amounts come from ``suggested_lock_usdt``.
"""

from __future__ import annotations

from .data import DailySnapshot, load_daily_snapshots, load_btc_bars
from .metrics import StrategyMetrics, compute_metrics, compare_strategies
from .runner import BacktestResult, run_action_plan_backtest
from .journal import attach_forward_returns

__all__ = [
    "DailySnapshot",
    "load_daily_snapshots",
    "load_btc_bars",
    "StrategyMetrics",
    "compute_metrics",
    "compare_strategies",
    "BacktestResult",
    "run_action_plan_backtest",
    "attach_forward_returns",
]
