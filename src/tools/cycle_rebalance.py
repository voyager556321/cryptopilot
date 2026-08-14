"""CLI dry-run for cycle-aware rebalance (advice only).

Usage:
  python -m src.tools.cycle_rebalance
  python -m src.tools.cycle_rebalance --execute   # stub — not implemented
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.data.market import fetch_portfolio_snapshot
from src.portfolio.season import assess_market_season
from src.portfolio.rebalance_hints import rebalance_from_portfolio


def _credentials(config):
    import os
    try:
        import config as root_config
        api_key = root_config.API_KEY or ""
        api_secret = root_config.API_SECRET or ""
    except Exception:
        api_key = os.getenv("EXCHANGE_API_KEY") or os.getenv("BINANCE_API_KEY") or ""
        api_secret = os.getenv("EXCHANGE_API_SECRET") or os.getenv("BINANCE_API_SECRET") or ""
    return api_key, api_secret


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cycle-aware rebalance dry-run (no orders)")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Stub for future live execution — not implemented",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "news_dip.yaml",
    )
    args = parser.parse_args(argv)

    if args.execute:
        print("ERROR: --execute is a stub. No orders are sent. Dry-run only.")
        return 2

    config = load_config(args.config if args.config.exists() else None)
    cr = config.cycle_rebalance
    out = Path(config.output_dir)

    season = assess_market_season(cr, output_dir=out, fetch=bool(cr.enabled))
    print(f"Season: {season.get('headline')}")
    if season.get("phase_changed"):
        print(
            f"WARNING: phase changed "
            f"{season.get('previous_phase')} → {season.get('phase')} — confirm before acting."
        )

    api_key, api_secret = _credentials(config)
    if not api_key or not api_secret:
        print("No Binance keys — showing season targets only.")
        for sym, pct in sorted((season.get("targets") or {}).items()):
            print(f"  {sym:6} target {pct:5.1f}%")
        return 0

    portfolio = fetch_portfolio_snapshot(
        api_key, api_secret, (config.exchange.name or "binance")
    )
    if not portfolio or not portfolio.get("available"):
        print(portfolio.get("message") if portfolio else "Portfolio unavailable")
        return 1

    view = rebalance_from_portfolio(
        portfolio,
        targets=season.get("targets"),
        thresholds_pct=cr.thresholds_pct,
        no_refill=cr.no_refill,
        min_action_usdt=float(cr.min_action_usdt),
        season=season,
    )
    print(view.get("policy") or "")
    print(
        f"{'Asset':6} {'Act':5} {'Cur%':7} {'Tgt%':7} {'Drift':8} {'USDT':10} Note"
    )
    print("-" * 72)
    rows = list(view.get("actionable") or []) + list(view.get("minor") or [])
    if not rows:
        print("(all within bands)")
        return 0
    for r in rows:
        print(
            f"{r['asset']:6} {r['action']:5} {r['current_pct']:7.2f} "
            f"{r['target_pct']:7.1f} {r['deviation_pct']:+8.1f} "
            f"{r['amount_usdt']:+10.2f} {r.get('note') or ''}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
