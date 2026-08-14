import { NextResponse } from "next/server";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Entry = {
  email: string;
  source: string;
  created_at: string;
};

function textFor(entry: Entry): string {
  return `CryptoPilot waitlist: ${entry.email}\n${entry.source} · ${entry.created_at}`;
}

async function postJson(url: string, body: unknown, headers?: Record<string, string>) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const t = await r.text().catch(() => "");
    throw new Error(`${r.status} ${t}`.trim());
  }
}

async function notify(entry: Entry): Promise<number> {
  let sent = 0;
  const errors: string[] = [];

  const webhook = process.env.WAITLIST_WEBHOOK_URL;
  if (webhook) {
    try {
      const discord = /discord(?:app)?\.com\/api\/webhooks/i.test(webhook);
      await postJson(
        webhook,
        discord
          ? { username: "CryptoPilot", content: textFor(entry) }
          : { text: textFor(entry), ...entry }
      );
      sent += 1;
    } catch (err) {
      errors.push(`webhook: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  const tgToken = process.env.WAITLIST_TELEGRAM_BOT_TOKEN;
  const tgChat = process.env.WAITLIST_TELEGRAM_CHAT_ID;
  if (tgToken && tgChat) {
    try {
      await postJson(`https://api.telegram.org/bot${tgToken}/sendMessage`, {
        chat_id: tgChat,
        text: textFor(entry),
      });
      sent += 1;
    } catch (err) {
      errors.push(`telegram: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  const resendKey = process.env.RESEND_API_KEY;
  const notifyEmail = process.env.WAITLIST_NOTIFY_EMAIL;
  if (resendKey && notifyEmail) {
    try {
      await postJson(
        "https://api.resend.com/emails",
        {
          from: process.env.WAITLIST_FROM_EMAIL || "CryptoPilot <onboarding@resend.dev>",
          to: [notifyEmail],
          subject: `Waitlist: ${entry.email}`,
          text: textFor(entry),
        },
        { Authorization: `Bearer ${resendKey}` }
      );
      sent += 1;
    } catch (err) {
      errors.push(`resend: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  if (errors.length) {
    console.error("WAITLIST_NOTIFY_ERRORS", errors);
  }
  if (!sent) {
    console.log("WAITLIST_SIGNUP_UNROUTED", JSON.stringify(entry));
  }
  return sent;
}

export async function POST(req: Request) {
  let payload: { email?: string; source?: string } = {};
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const email = String(payload.email || "")
    .trim()
    .toLowerCase();
  const source = String(payload.source || "landing").trim() || "landing";

  if (!EMAIL_RE.test(email)) {
    return NextResponse.json({ error: "Invalid email address" }, { status: 400 });
  }

  const configured = Boolean(
    process.env.WAITLIST_WEBHOOK_URL ||
      (process.env.WAITLIST_TELEGRAM_BOT_TOKEN && process.env.WAITLIST_TELEGRAM_CHAT_ID) ||
      (process.env.RESEND_API_KEY && process.env.WAITLIST_NOTIFY_EMAIL)
  );

  const entry: Entry = {
    email,
    source,
    created_at: new Date().toISOString(),
  };

  const sent = configured ? await notify(entry) : 0;
  if (configured && sent === 0) {
    return NextResponse.json(
      { error: "Could not save signup. Try again later." },
      { status: 502 }
    );
  }

  return NextResponse.json({
    ok: true,
    email,
    message: "You're on the list. We'll be in touch.",
    persisted: sent > 0,
  });
}
