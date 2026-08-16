"use client";

import { FormEvent, useState } from "react";
import { track } from "@vercel/analytics";

const PROBLEMS = [
  { value: "", label: "What is your biggest portfolio problem today?" },
  { value: "exits", label: "Don't know when to take profits / exits" },
  { value: "emotion", label: "Emotional decisions (fear & greed)" },
  { value: "allocation", label: "Allocation / rebalancing discipline" },
  { value: "risk", label: "Risk / USDT cushion / drawdowns" },
  { value: "noise", label: "Too many signals, no daily process" },
  { value: "other", label: "Something else" },
];

export default function WaitlistForm({ source = "landing" }: { source?: string }) {
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const email = String(data.get("email") || "").trim();
    const problem = String(data.get("problem") || "").trim();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setKind("err");
      setStatus("Enter a valid email address.");
      return;
    }
    if (!problem) {
      setKind("err");
      setStatus("Pick your biggest portfolio problem today.");
      return;
    }
    setBusy(true);
    setKind("");
    setStatus("Joining…");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source, problem }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.error || body.message || res.statusText);
      }
      setKind("ok");
      setStatus(body.message || "You're on the list. We'll be in touch.");
      form.reset();
      track("WaitlistSignup", { source, problem });
    } catch (err) {
      setKind("err");
      setStatus(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form className="lp-form lp-form-stack" onSubmit={onSubmit} noValidate>
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
        <label className="lp-sr-only" htmlFor="waitlist-problem">
          What is your biggest portfolio problem today?
        </label>
        <select
          id="waitlist-problem"
          name="problem"
          required
          defaultValue=""
          aria-describedby="waitlist-status"
        >
          {PROBLEMS.map((p) => (
            <option key={p.value || "empty"} value={p.value} disabled={p.value === ""}>
              {p.label}
            </option>
          ))}
        </select>
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
