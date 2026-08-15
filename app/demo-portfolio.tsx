"use client";

import { useState } from "react";
import { track } from "@vercel/analytics";

type DemoScenario = {
  id: string;
  label: string;
  hint: string;
  portfolioValue: string;
  action: string;
  move: string;
  reasons: string[];
  tone: "lock" | "hold" | "defense";
};

const SCENARIOS: DemoScenario[] = [
  {
    id: "profit_lock",
    label: "Green day",
    hint: "Book is up · lock some gains",
    portfolioValue: "$5,000",
    action: "PROFIT LOCK",
    move: "Move $18 to USDT",
    reasons: [
      "BTC risk-off",
      "Daily PnL +$54",
      "USDT below target",
      "Lock ~30% of today's gain",
    ],
    tone: "lock",
  },
  {
    id: "hold",
    label: "Quiet day",
    hint: "No strong signal · do nothing",
    portfolioValue: "$5,000",
    action: "HOLD",
    move: "No trade required. Stick to the plan.",
    reasons: [
      "BTC neutral",
      "USDT still below cushion",
      "No strong lock trigger",
      "Avoid reacting to noise",
    ],
    tone: "hold",
  },
  {
    id: "defense",
    label: "Red day",
    hint: "Book is down · protect cushion",
    portfolioValue: "$5,000",
    action: "DEFENSE",
    move: "Trim risk · protect cushion",
    reasons: [
      "Daily PnL −$62",
      "BTC bounce_watch inside drawdown",
      "USDT below target",
      "Cut satellites first · protect BTC/ETH",
    ],
    tone: "defense",
  },
];

export default function DemoPortfolio() {
  const [active, setActive] = useState(0);
  const [seen, setSeen] = useState(false);
  const scenario = SCENARIOS[active];

  function selectDay(index: number) {
    setActive(index);
    if (!seen) {
      setSeen(true);
      track("DemoOpened");
    }
    track("DemoScenario", { scenario: SCENARIOS[index].id });
  }

  return (
    <section className="lp-section lp-section-alt" id="demo" aria-labelledby="demo-title">
      <div className="lp-wrap">
        <p className="lp-eyebrow lp-center">Try before you join</p>
        <h2 id="demo-title" className="lp-center">
          Try Demo Portfolio
        </h2>
        <p className="lp-lede-sm lp-center">
          Tap a market day. The action changes. Same rule engine shape as the product —
          sample book, not live prices.
        </p>

        <div className="lp-demo">
          <p className="lp-demo-prompt">Switch the day → watch ACTION change</p>
          <div className="lp-demo-days" role="tablist" aria-label="Demo market day">
            {SCENARIOS.map((s, i) => (
              <button
                key={s.id}
                type="button"
                role="tab"
                aria-selected={i === active}
                className={"lp-demo-day" + (i === active ? " is-active" : "")}
                onClick={() => selectDay(i)}
              >
                <span className="lp-demo-day-label">{s.label}</span>
                <span className="lp-demo-day-action">{s.action}</span>
              </button>
            ))}
          </div>

          <div className="lp-demo-card" role="tabpanel" key={scenario.id}>
            <div className="lp-demo-meta">
              <div>
                <span className="lp-demo-meta-label">Portfolio value</span>
                <p className="lp-demo-meta-hint">{scenario.hint}</p>
              </div>
              <span className="lp-demo-meta-value">{scenario.portfolioValue}</span>
            </div>

            <div className={"lp-product-card lp-demo-product lp-demo-tone-" + scenario.tone}>
              <div className="lp-product-top">
                <span className="lp-product-day">TODAY</span>
                <span className="lp-product-tag">Sample scenario</span>
              </div>
              <p className="lp-product-action">ACTION: {scenario.action}</p>
              <p className="lp-product-sub">{scenario.move}</p>
              <p className="lp-product-reasons-label">Why</p>
              <ul className="lp-product-reasons">
                {scenario.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p className="lp-product-footer">
                Illustrative · same decision types as production · not a live feed
              </p>
            </div>

            <div className="lp-demo-cta">
              <p className="lp-mantra lp-demo-ask">
                Want this recommendation for your portfolio?
              </p>
              <a
                className="lp-btn"
                href="#waitlist"
                onClick={() => track("DemoToWaitlist", { scenario: scenario.id })}
              >
                Get Early Access
              </a>
              <p className="lp-fine">
                <a href="#trust">Why trust the engine?</a>
                {" · "}
                Open the app. Know what to do today.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
