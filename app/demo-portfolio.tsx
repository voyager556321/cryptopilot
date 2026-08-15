"use client";

import { useState } from "react";
import { track } from "@vercel/analytics";

type DemoScenario = {
  id: string;
  label: string;
  portfolioValue: string;
  action: string;
  move: string;
  reasons: string[];
  footer: string;
};

const SCENARIOS: DemoScenario[] = [
  {
    id: "profit_lock",
    label: "Green day",
    portfolioValue: "$5,000",
    action: "PROFIT LOCK",
    move: "Move $18 to USDT",
    reasons: [
      "BTC risk-off",
      "Daily PnL +$54",
      "USDT below target",
      "Lock ~30% of today's gain",
    ],
    footer: "Demo portfolio · advice only · no auto-orders",
  },
  {
    id: "hold",
    label: "Quiet day",
    portfolioValue: "$5,000",
    action: "HOLD",
    move: "No trade required. Stick to the plan.",
    reasons: [
      "BTC neutral",
      "USDT still below cushion",
      "No strong lock trigger",
      "Avoid reacting to noise",
    ],
    footer: "Demo portfolio · advice only · no auto-orders",
  },
  {
    id: "defense",
    label: "Red day",
    portfolioValue: "$5,000",
    action: "DEFENSE",
    move: "Trim risk · protect cushion",
    reasons: [
      "Daily PnL −$62",
      "BTC bounce_watch inside drawdown",
      "USDT below target",
      "Cut satellites first · protect BTC/ETH",
    ],
    footer: "Demo portfolio · advice only · no auto-orders",
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
          See today&apos;s decision on a sample book — no email, no Binance, no signup.
        </p>

        <div className="lp-demo">
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
                {s.label}
              </button>
            ))}
          </div>

          <div className="lp-demo-card" role="tabpanel">
            <div className="lp-demo-meta">
              <span className="lp-demo-meta-label">Portfolio value</span>
              <span className="lp-demo-meta-value">{scenario.portfolioValue}</span>
            </div>

            <div className="lp-product-card lp-demo-product">
              <div className="lp-product-top">
                <span className="lp-product-day">TODAY</span>
                <span className="lp-product-tag">Demo decision</span>
              </div>
              <p className="lp-product-action">ACTION: {scenario.action}</p>
              <p className="lp-product-sub">{scenario.move}</p>
              <p className="lp-product-reasons-label">Why</p>
              <ul className="lp-product-reasons">
                {scenario.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p className="lp-product-footer">{scenario.footer}</p>
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
                Open the app. Know what to do today. · Read-only later — no auto-orders.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
