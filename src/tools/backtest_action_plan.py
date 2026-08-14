"""CLI: backtest production build_action_plan on portfolio_history.csv.

Usage:
  python -m src.tools.backtest_action_plan
  python -m src.tools.backtest_action_plan --history out/portfolio_history.csv --out out/backtest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.portfolio.backtest import run_action_plan_backtest
from src.portfolio.backtest.data import load_btc_bars, load_daily_snapshots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backtest production build_action_plan() vs buy&hold / USDT-heavy"
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=ROOT / "out" / "portfolio_history.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "out" / "backtest",
    )
    parser.add_argument(
        "--btc-cache",
        type=Path,
        default=ROOT / "out" / "backtest" / "btc_bars.json",
    )
    parser.add_argument("--no-fetch", action="store_true", help="Use cache only (no Binance)")
    parser.add_argument("--usdt-heavy-pct", type=float, default=50.0)
    parser.add_argument("--alt-beta", type=float, default=1.25)
    args = parser.parse_args(argv)

    snaps = load_daily_snapshots(args.history)
    if len(snaps) < 3:
        print(f"Need ≥3 daily snapshots in {args.history} (got {len(snaps)})", file=sys.stderr)
        return 1

    bars = load_btc_bars(cache_path=args.btc_cache, fetch=not args.no_fetch)
    if len(bars) < 30:
        print(
            "Need ≥30 BTC daily bars (fetch failed or --no-fetch without cache).",
            file=sys.stderr,
        )
        return 1

    result = run_action_plan_backtest(
        snaps,
        btc_bars=bars,
        usdt_heavy_pct=args.usdt_heavy_pct,
        alt_beta=args.alt_beta,
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "journal.json").write_text(
        json.dumps(result.journal, indent=2), encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(
            {
                "meta": result.meta,
                "metrics": result.metrics,
                "action_forward_summary": result.action_forward_summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "equity.json").write_text(
        json.dumps(result.equity, indent=2), encoding="utf-8"
    )

    print(f"Wrote {out}/summary.json, journal.json, equity.json")
    print(f"Days {result.meta['start']} → {result.meta['end']} ({result.meta['days']})")
    for row in result.metrics.get("strategies") or []:
        print(
            f"  {row['name']:12}  ret={row['total_return']*100:+.2f}%  "
            f"mdd={row['max_drawdown']*100:.2f}%  "
            f"locks={row.get('profit_locks', 0)}  "
            f"locked=${row.get('locked_usdt_total', 0):.0f}"
        )
    print("Forward outcomes by action:")
    for action, stats in (result.action_forward_summary or {}).items():
        print(
            f"  {action:12} n={stats['count']}  "
            f"down_3d={stats['pct_down_3d']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
