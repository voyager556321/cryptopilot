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

### Waitlist notifications

The form does **not** email you by itself. Set env vars in Vercel → Settings → Environment Variables (Production + Preview), then Redeploy.

**Telegram (найпростіше):**

1. Telegram → [@BotFather](https://t.me/BotFather) → `/newbot` → скопіюй token.
2. Напиши боту будь-яке повідомлення.
3. Відкрий `https://api.telegram.org/bot<TOKEN>/getUpdates` — візьми `chat.id`.
4. У Vercel додай:

```
WAITLIST_TELEGRAM_BOT_TOKEN=123456:ABC...
WAITLIST_TELEGRAM_CHAT_ID=123456789
```

Альтернативи: `WAITLIST_WEBHOOK_URL` (Discord Incoming Webhook) або `RESEND_API_KEY` + `WAITLIST_NOTIFY_EMAIL`.

Do **not** deploy the FastAPI dashboard to Vercel.

## Backtest (validate ``build_action_plan``)

Uses the **same** production function as `/api/overview` — no parallel strategy.

```bash
python -m src.tools.backtest_action_plan
# writes out/backtest/{summary,journal,equity}.json
```

Compares **CryptoPilot** (simulated profit-lock execution) vs **Buy & Hold** vs **USDT-heavy (50%)** on:

- total return / CAGR
- max drawdown
- volatility / Sharpe
- profit locks, locked USDT, trades, missed upside vs buy&hold

Journal rows include action + reasons and forward returns **1d / 3d / 7d**.

Honest limit: history CSV has sleeve % only (no per-coin bags); bags are reconstructed for trim ordering.

## Tests

```bash
pytest tests/ -q
```
