"""Performance metrics for backtest equity curves."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class StrategyMetrics:
    name: str
    start_equity: float
    end_equity: float
    total_return: float
    cagr: Optional[float]
    max_drawdown: float
    volatility_ann: Optional[float]
    sharpe: Optional[float]
    days: int
    profit_locks: int = 0
    locked_usdt_total: float = 0.0
    trades: int = 0
    missed_upside: Optional[float] = None  # vs buy&hold end equity, if provided

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _daily_returns(equity: Sequence[float]) -> List[float]:
    out: List[float] = []
    for i in range(1, len(equity)):
        a, b = float(equity[i - 1]), float(equity[i])
        if a <= 0:
            out.append(0.0)
        else:
            out.append(b / a - 1.0)
    return out


def max_drawdown(equity: Sequence[float]) -> float:
    peak = float("-inf")
    mdd = 0.0
    for v in equity:
        x = float(v)
        if x > peak:
            peak = x
        if peak > 0:
            dd = x / peak - 1.0
            if dd < mdd:
                mdd = dd
    return mdd


def compute_metrics(
    name: str,
    equity: Sequence[float],
    *,
    days: Optional[int] = None,
    profit_locks: int = 0,
    locked_usdt_total: float = 0.0,
    trades: int = 0,
    buy_hold_end: Optional[float] = None,
) -> StrategyMetrics:
    eq = [float(x) for x in equity]
    if not eq:
        return StrategyMetrics(
            name=name,
            start_equity=0.0,
            end_equity=0.0,
            total_return=0.0,
            cagr=None,
            max_drawdown=0.0,
            volatility_ann=None,
            sharpe=None,
            days=0,
        )
    start, end = eq[0], eq[-1]
    n = days if days is not None else max(0, len(eq) - 1)
    total_ret = (end / start - 1.0) if start > 0 else 0.0
    cagr = None
    if n > 0 and start > 0 and end > 0:
        cagr = (end / start) ** (365.0 / n) - 1.0
    rets = _daily_returns(eq)
    vol = None
    sharpe = None
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = math.sqrt(var)
        vol = std * math.sqrt(365.0)
        if std > 1e-12:
            sharpe = (mean / std) * math.sqrt(365.0)
    missed = None
    if buy_hold_end is not None and end is not None:
        missed = float(buy_hold_end) - float(end)
    return StrategyMetrics(
        name=name,
        start_equity=round(start, 2),
        end_equity=round(end, 2),
        total_return=round(total_ret, 6),
        cagr=None if cagr is None else round(cagr, 6),
        max_drawdown=round(max_drawdown(eq), 6),
        volatility_ann=None if vol is None else round(vol, 6),
        sharpe=None if sharpe is None else round(sharpe, 4),
        days=n,
        profit_locks=profit_locks,
        locked_usdt_total=round(float(locked_usdt_total), 2),
        trades=trades,
        missed_upside=None if missed is None else round(missed, 2),
    )


def compare_strategies(rows: Sequence[StrategyMetrics]) -> Dict[str, Any]:
    return {
        "strategies": [r.as_dict() for r in rows],
        "best_total_return": max(rows, key=lambda r: r.total_return).name if rows else None,
        "best_max_drawdown": max(rows, key=lambda r: r.max_drawdown).name if rows else None,  # least negative
        "note": (
            "CryptoPilot thesis is risk-adjusted behavior (drawdown / discipline), "
            "not maximum absolute return."
        ),
    }
