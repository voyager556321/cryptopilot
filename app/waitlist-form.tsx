"use client";

import { FormEvent, useState } from "react";
import { track } from "@vercel/analytics";

export default function WaitlistForm({ source = "landing" }: { source?: string }) {
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const email = String(new FormData(form).get("email") || "").trim();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setKind("err");
      setStatus("Enter a valid email address.");
      return;
    }
    setBusy(true);
    setKind("");
    setStatus("Joining…");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.error || body.message || res.statusText);
      }
      setKind("ok");
      setStatus(body.message || "You're on the list. We'll be in touch.");
      form.reset();
      track("WaitlistSignup", { source });
    } catch (err) {
      setKind("err");
      setStatus(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form className="lp-form" onSubmit={onSubmit} noValidate>
        <label className="lp-sr-only" htmlFor="waitlist-email">
          Email
        </label>
        <input
          id="waitlist-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          placeholder="you@email.com"
          aria-describedby="waitlist-status"
        />
        <button className="lp-btn lp-btn-lg" type="submit" disabled={busy}>
          Get Early Access
        </button>
      </form>
      <p
        className={"lp-form-status" + (kind ? ` is-${kind}` : "")}
        id="waitlist-status"
        role="status"
        aria-live="polite"
      >
        {status}
      </p>
    </>
  );
}
