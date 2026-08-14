# CryptoPilot landing → Vercel

Тільки маркетинг-сторінка + waitlist. Дашборд / Binance сюди **не** деплоїти.

## Швидкий старт

```bash
cd deploy/vercel
npx vercel
```

Продакшен:

```bash
npx vercel --prod
```

Або: [vercel.com/new](https://vercel.com/new) → Import Git repo → Root Directory = `deploy/vercel`.

## Що отримаєш

| URL | Що |
|-----|-----|
| `/` | Лендінг |
| `/landing` | Redirect на `/` |
| `/api/waitlist` | POST `{ "email": "..." }` |

## Waitlist (обов’язково для продакшену)

На Vercel файлова система **не постійна** — `out/waitlist.json` не спрацює.

У Project Settings → Environment Variables додай:

```
WAITLIST_WEBHOOK_URL=https://...
```

Підходить Discord Incoming Webhook, Slack, n8n, Make, Zapier.

Без змінної форма все одно відповість «You're on the list», але email лише в логах функції (Vercel → Deployments → Functions → Logs).

## Домен

Vercel → Project → Domains → додай `cryptopilot.app` (або свій) і пропиши DNS як покаже Vercel.

## Чого тут немає

- Crypto / IBKR дашборд
- Binance API keys
- Фоновий портфоліо-синк

Це лишається локально або на VPS / Railway / Render.
