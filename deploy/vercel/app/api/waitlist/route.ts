import { NextResponse } from "next/server";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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

  const webhook = process.env.WAITLIST_WEBHOOK_URL;
  const entry = {
    email,
    source,
    created_at: new Date().toISOString(),
  };

  if (webhook) {
    try {
      const r = await fetch(webhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: `Waitlist: **${email}** (${source})`,
          username: "CryptoPilot Waitlist",
          ...entry,
        }),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "");
        console.error("waitlist webhook failed", r.status, text);
        return NextResponse.json(
          { error: "Could not save signup. Try again later." },
          { status: 502 }
        );
      }
    } catch (err) {
      console.error("waitlist webhook error", err);
      return NextResponse.json(
        { error: "Could not save signup. Try again later." },
        { status: 502 }
      );
    }
  } else {
    console.log("WAITLIST_SIGNUP", JSON.stringify(entry));
  }

  return NextResponse.json({
    ok: true,
    email,
    message: "You're on the list. We'll be in touch.",
    persisted: Boolean(webhook),
  });
}
