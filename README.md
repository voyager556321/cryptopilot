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

## Config

Copy [`.env.example`](.env.example) → `.env`:

| Key | Purpose |
|-----|---------|
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | Portfolio sync (read) |
| `IBKR_FLEX_TOKEN` / `IBKR_FLEX_QUERY_ID` | Flex open-positions sync |
| `IBKR_ACCOUNT_ID` | Optional account hint |

Strategy / alert settings: [`configs/news_dip.yaml`](configs/news_dip.yaml).

## Layout

```
src/web/          FastAPI + HTML/JS
src/portfolio/    Crypto action plan, history, paper journal
src/ibkr/         IBKR snapshot, Flex, rebalance / hybrid hints
src/news_dip_bot.py  Background news+dip / paper loop for Crypto UI
configs/          news_dip.yaml
out/              Runtime state (ledgers, snapshots) — gitignored
```

## Tests

```bash
pytest tests/ -q
```
