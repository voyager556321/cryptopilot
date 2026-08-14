/**
 * Vercel serverless waitlist endpoint.
 * Persistence: set WAITLIST_WEBHOOK_URL (Discord / Slack / n8n / Make / Zapier).
 * Local out/waitlist.json does not work on Vercel (ephemeral filesystem).
 */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function json(res, status, body) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  if (req.body && typeof req.body === "object") return req.body;
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) return {};
  return JSON.parse(raw);
}

module.exports = async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    res.end();
    return;
  }

  if (req.method !== "POST") {
    json(res, 405, { error: "Method not allowed" });
    return;
  }

  let payload;
  try {
    payload = await readJson(req);
  } catch {
    json(res, 400, { error: "Invalid JSON body" });
    return;
  }

  const email = String(payload.email || "")
    .trim()
    .toLowerCase();
  const source = String(payload.source || "landing").trim() || "landing";

  if (!EMAIL_RE.test(email)) {
    json(res, 400, { error: "Invalid email address" });
    return;
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
        json(res, 502, { error: "Could not save signup. Try again later." });
        return;
      }
    } catch (err) {
      console.error("waitlist webhook error", err);
      json(res, 502, { error: "Could not save signup. Try again later." });
      return;
    }
  } else {
    // Without a webhook, signup is accepted but not persisted across deploys.
    console.log("WAITLIST_SIGNUP", JSON.stringify(entry));
  }

  json(res, 200, {
    ok: true,
    email,
    message: "You're on the list. We'll be in touch.",
    persisted: Boolean(webhook),
  });
};
