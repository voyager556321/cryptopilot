# Trading dashboard (local UI)

Advice-only local dashboard for **Crypto (Binance)** and **IBKR stocks**.  
No auto-orders — Sync / Flex update snapshots; you place trades yourself.

## Run

```bash
cd /home/admin/trading
source .venv/bin/activate
pip install -r requirements.txt   # first time
python -m src.web
```

Open:
- Crypto: http://127.0.0.1:8000/
- IBKR:   http://127.0.0.1:8000/ibkr
- Landing (marketing): http://127.0.0.1:8000/landing

## Config

Copy [`.env.example`](.env.example) → `.env`:

| Key | Purpose |
|-----|---------|
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | Portfolio sync (read) |
| `IBKR_FLEX_TOKEN` / `IBKR_FLEX_QUERY_ID` | Flex open-positions sync |
| `IBKR_ACCOUNT_ID` | Optional account hint |

Strategy / alert settings: [`configs/news_dip.yaml`](configs/news_dip.yaml).

### Structure cycle vs season (two layers)

| Layer | Module | Drives |
|-------|--------|--------|
| **Price structure** | `src/portfolio/market_cycle.py` | USDT cushion / profit-lock urgency (`risk_off`, `bounce_watch`, …) |
| **BTC/Alt season** | `src/portfolio/season.py` + CoinGecko | **Rebalance target weights** (`btc_season` / `neutral` / `alt_season`) |

Season rules (editable in YAML `cycle_rebalance`):

- **BTC season:** BTC dominance **rising** and alt-index &lt; 25
- **Alt season:** BTC dominance **falling** and alt-index &gt; 75
- **Neutral:** everything else (incl. conflicting signals)

Alt-index proxy = % of top alts whose 90d return beat BTC (CoinGecko markets).  
Satellites `AAVE/LINK/FIL/XRP`: sell if overweight vs phase target, **never buy back**.

Phase targets live under `cycle_rebalance.phases.*` in the YAML.

Dry-run CLI:

```bash
python -m src.tools.cycle_rebalance
# --execute is a stub (no orders)
```

## Layout

```
app/              Next.js marketing landing (Vercel)
src/web/          FastAPI + HTML/JS (local dashboard)
src/portfolio/    Action plan, history, season, rebalance, paper
src/tools/        CLI helpers (cycle_rebalance dry-run)
src/ibkr/         IBKR snapshot, Flex, rebalance / hybrid hints
src/news_dip_bot.py  Background news+dip / paper loop for Crypto UI
configs/          news_dip.yaml (incl. cycle_rebalance)
out/              Runtime state (ledgers, season_cache, snapshots) — gitignored
```

## Vercel (public landing)

The public site is the Next.js app at the **repository root** (`app/`, `package.json`).

1. Import `voyager556321/cryptopilot` in Vercel.
2. **Root Directory** — empty.
3. **Build & Development Settings** (критично):
   - Framework Preset: **Next.js** (не Other)
   - Output Directory: **вимкни Override** — не `public`
   - Build Command: `next build` (або дефолт Next.js)
4. Production: latest Ready deploy → **Promote to Production**.

Env (optional waitlist): `WAITLIST_WEBHOOK_URL`.

Do **not** deploy the FastAPI dashboard to Vercel.

## Tests

```bash
pytest tests/ -q
```
