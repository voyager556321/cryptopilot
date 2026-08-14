# CryptoPilot landing → Vercel (Next.js)

Маркетинг-сторінка + waitlist. Дашборд / Binance сюди **не** деплоїти.

## Швидкий старт

```bash
cd deploy/vercel
npm install
npm run dev
```

Продакшен:

```bash
npx vercel --prod
```

Або: [vercel.com/new](https://vercel.com/new) → Import Git repo → **Root Directory** = `deploy/vercel`.
Framework має визначитись як **Next.js**.

## Що отримаєш

| URL | Що |
|-----|-----|
| `/` | Лендінг |
| `/landing` | Redirect на `/` |
| `/api/waitlist` | POST `{ "email": "..." }` |

## Analytics

У `app/layout.tsx`:

```tsx
import { Analytics } from "@vercel/analytics/next"
```

1. Увімкни **Web Analytics** у проєкті Vercel.
2. Framework у підказках: **Next.js**.
3. Після деплою відкрий сайт — pageviews збираються самі; waitlist шле подію `WaitlistSignup`.

## Waitlist

У Project Settings → Environment Variables:

```
WAITLIST_WEBHOOK_URL=https://...
```

Discord / Slack / n8n / Make / Zapier. Без змінної email лише в логах функції.

## Домен

Vercel → Project → Domains. `*.vercel.app` безкоштовно; свій домен — опційно.
