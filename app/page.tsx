import Nav from "./nav";
import DemoPortfolio from "./demo-portfolio";
import WaitlistForm from "./waitlist-form";

export default function HomePage() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Nav />

      <p className="lp-sticky-msg" role="note">
        <span>Open the app.</span>
        <span className="lp-sticky-sep" aria-hidden="true">
          ·
        </span>
        <strong>Know what to do today.</strong>
      </p>

      <main id="main">
        <section className="lp-hero" aria-labelledby="hero-title">
          <div className="lp-wrap lp-hero-grid lp-hero-product">
            <div className="lp-hero-visual" aria-hidden="true">
              <div className="lp-product-card">
                <div className="lp-product-top">
                  <span className="lp-product-day">TODAY</span>
                  <span className="lp-product-tag">Daily decision</span>
                </div>
                <p className="lp-product-action">ACTION: PROFIT LOCK</p>
                <p className="lp-product-sub">Move $18 to USDT</p>
                <p className="lp-product-reasons-label">Why</p>
                <ul className="lp-product-reasons">
                  <li>BTC risk-off</li>
                  <li>Daily PnL +$54</li>
                  <li>USDT below target</li>
                  <li>Lock ~30% of today&apos;s gain</li>
                </ul>
                <p className="lp-product-footer">Hold · Profit lock · Defense · Rebalance</p>
              </div>
            </div>

            <div className="lp-hero-copy">
              <p className="lp-eyebrow">Portfolio discipline engine · not a trading bot</p>
              <h1 id="hero-title">Know what to do with your crypto portfolio today.</h1>
              <p className="lp-lede">
                Help yourself follow your own rules — hold, lock profit, defend, rebalance —
                when greed or fear would otherwise decide. Advice only. No signals. No auto-orders.
              </p>
              <p className="lp-mantra">Open the app. Know what to do today.</p>
              <div className="lp-hero-cta">
                <a className="lp-btn" href="#demo">
                  Try Demo Portfolio
                </a>
                <a className="lp-btn lp-btn-ghost" href="#trust">
                  Why trust this?
                </a>
              </div>
              <p className="lp-fine">
                Demo first (no email).{" "}
                <a href="#before-after">See the +$54 day → lock example.</a>
              </p>
            </div>
          </div>
        </section>

        <DemoPortfolio />

        <section className="lp-section" id="before-after" aria-labelledby="ba-title">
          <div className="lp-wrap">
            <h2 id="ba-title" className="lp-center">
              Same green day. Different outcome.
            </h2>
            <p className="lp-lede-sm lp-center">
              Portfolio discipline — not a forecast of the top.
            </p>
            <div className="lp-ba">
              <article className="lp-ba-card lp-ba-before">
                <h3>Without LockIn</h3>
                <p className="lp-ba-stat">Portfolio +$54 today</p>
                <ul className="lp-ba-chaos">
                  <li>Do nothing</li>
                  <li>Get greedy</li>
                  <li>Hope it keeps going</li>
                </ul>
                <p className="lp-ba-verdict">
                  Result: emotion decides.
                  <br />
                  No process.
                </p>
              </article>
              <div className="lp-ba-arrow" aria-hidden="true">
                →
              </div>
              <article className="lp-ba-card lp-ba-after">
                <h3>With LockIn</h3>
                <p className="lp-ba-stat lp-ba-stat-muted">Portfolio +$54 today</p>
                <div className="lp-ba-rec">
                  <span className="lp-product-day">TODAY</span>
                  <p className="lp-product-action lp-product-action-sm">ACTION: PROFIT LOCK</p>
                  <p className="lp-product-sub">Move $18 to USDT</p>
                  <p className="lp-product-reasons-label">Reason</p>
                  <ul className="lp-product-reasons">
                    <li>USDT below target</li>
                    <li>Profit lock incomplete</li>
                    <li>BTC risk-off</li>
                  </ul>
                </div>
                <p className="lp-ba-verdict lp-ba-verdict-ok">
                  Result: rules executed.
                  <br />
                  Discipline held.
                </p>
              </article>
            </div>
          </div>
        </section>

        <section className="lp-section lp-section-alt" id="problem" aria-labelledby="problem-title">
          <div className="lp-wrap">
            <h2 id="problem-title">
              Most crypto investors don&apos;t fail because they picked the wrong coin.
            </h2>
            <div className="lp-cards-3">
              <article className="lp-card">
                <h3>No process</h3>
                <p>You know how to buy. You don&apos;t have a daily rule for hold, lock, or defend.</p>
              </article>
              <article className="lp-card">
                <h3>Emotion wins</h3>
                <p>Fear and greed fill the gap when there&apos;s no plan for today.</p>
              </article>
              <article className="lp-card">
                <h3>Noise, not decisions</h3>
                <p>
                  News and charts pile up. They rarely answer: what should I do with my portfolio
                  today?
                </p>
              </article>
            </div>
          </div>
        </section>

        <section className="lp-section" id="how" aria-labelledby="how-title">
          <div className="lp-wrap">
            <h2 id="how-title">How it works</h2>
            <p className="lp-lede-sm lp-center">
              Three steps to today&apos;s action — not another feed of indicators.
            </p>
            <div className="lp-steps">
              <article className="lp-step">
                <div className="lp-step-num" aria-hidden="true">
                  1
                </div>
                <div className="lp-step-icon" aria-hidden="true">
                  <svg viewBox="0 0 48 48" fill="none">
                    <rect x="8" y="12" width="32" height="24" rx="4" stroke="currentColor" strokeWidth="2" />
                    <path
                      d="M16 24h16M16 28h10"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
                <h3>Connect portfolio</h3>
                <p>Read-only Binance sync. Your balances, your allocation.</p>
              </article>
              <article className="lp-step">
                <div className="lp-step-num" aria-hidden="true">
                  2
                </div>
                <div className="lp-step-icon" aria-hidden="true">
                  <svg viewBox="0 0 48 48" fill="none">
                    <circle cx="24" cy="24" r="14" stroke="currentColor" strokeWidth="2" />
                    <path
                      d="M24 16v8l6 4"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
                <h3>Apply your rules</h3>
                <p>Risk cushion, profit-lock, defense, and rebalance — checked against today&apos;s market.</p>
              </article>
              <article className="lp-step">
                <div className="lp-step-num" aria-hidden="true">
                  3
                </div>
                <div className="lp-step-icon" aria-hidden="true">
                  <svg viewBox="0 0 48 48" fill="none">
                    <path
                      d="M14 28l6 6 14-16"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <rect x="10" y="10" width="28" height="28" rx="6" stroke="currentColor" strokeWidth="2" />
                  </svg>
                </div>
                <h3>Get today&apos;s action</h3>
                <p>Open the app. Know what to do today — with reasons.</p>
              </article>
            </div>
          </div>
        </section>

        <section className="lp-section lp-section-alt" id="outcomes" aria-labelledby="outcomes-title">
          <div className="lp-wrap">
            <h2 id="outcomes-title">What you get</h2>
            <p className="lp-lede-sm lp-center">Outcomes first. Features only as the means.</p>
            <div className="lp-features">
              <article className="lp-feature">
                <h3>Clarity</h3>
                <p>One daily action instead of ten open questions.</p>
              </article>
              <article className="lp-feature">
                <h3>Discipline</h3>
                <p>Hold, profit lock, defense, or rebalance — on a process, not a mood.</p>
              </article>
              <article className="lp-feature">
                <h3>Consistency</h3>
                <p>Same question every day: what should I do with my portfolio today?</p>
              </article>
              <article className="lp-feature">
                <h3>Risk management</h3>
                <p>Protect gains and cushion before chasing the next move.</p>
              </article>
              <article className="lp-feature">
                <h3>Explainable reasons</h3>
                <p>Every recommendation shows why — so you can trust the plan.</p>
              </article>
              <article className="lp-feature">
                <h3>You stay in control</h3>
                <p>Advice only. No auto-orders. You decide when to click sell.</p>
              </article>
            </div>
            <p className="lp-mantra lp-center lp-mantra-block">Open the app. Know what to do today.</p>
          </div>
        </section>

        <section className="lp-section" id="trust" aria-labelledby="trust-title">
          <div className="lp-wrap">
            <p className="lp-eyebrow lp-center">Credibility · not vibes</p>
            <h2 id="trust-title" className="lp-center">
              Why should you trust the recommendation?
            </h2>
            <p className="lp-lede-sm lp-center">
              You shouldn&apos;t — until the process is clear and the evidence is real.
              Here is what the system actually did. No invented performance.
            </p>

            <div className="lp-proof lp-proof-tight">
              <article className="lp-proof-item">
                <p className="lp-proof-num">4</p>
                <p className="lp-proof-label">Profit-lock actions executed on the founder book</p>
              </article>
              <article className="lp-proof-item">
                <p className="lp-proof-num">USDT</p>
                <p className="lp-proof-label">Profits systematically moved into reserves</p>
              </article>
              <article className="lp-proof-item">
                <p className="lp-proof-num">3 + 1</p>
                <p className="lp-proof-label">PROFIT LOCK + DEFENSE in the early replay</p>
              </article>
              <article className="lp-proof-item">
                <p className="lp-proof-num">Rules</p>
                <p className="lp-proof-label">Disciplined, not predictive · no auto-orders</p>
              </article>
            </div>

            <div className="lp-trust-grid">
              <article className="lp-trust-card">
                <h3>Disciplined, not predictive</h3>
                <p>
                  Consistency over prediction. Fixed rules: green day → consider profit lock;
                  deep red → defense; otherwise hold. We help you execute your process — not beat
                  the market with a crystal ball.
                </p>
              </article>
              <article className="lp-trust-card">
                <h3>Portfolio discipline engine</h3>
                <p>
                  Not a signals bot. Not auto-trading. One job: what should I do with{" "}
                  <em>my</em> portfolio <em>today</em>? Advice only. You stay in control.
                </p>
              </article>
              <article className="lp-trust-card">
                <h3>Founder&apos;s live book</h3>
                <p>
                  Four take-profit days logged (Aug 4–9): profits moved into USDT on purpose —
                  including ~$27, ~$20, ~$7, ~$5. The point is the habit, not the dollar headline.
                </p>
              </article>
              <article className="lp-trust-card">
                <h3>Too early to claim an edge</h3>
                <p>
                  Same production <code>build_action_plan()</code> on a short sleeve tape (Aug
                  2–14). Drawdown almost tied with buy&amp;hold. We say that out loud. Longer tape
                  → clearer behavior proof.
                </p>
              </article>
            </div>

            <div className="lp-history" id="history">
              <h3 className="lp-history-title">Recommendation history (early replay)</h3>
              <p className="lp-history-lede">
                What the engine advised on the founder sleeve tape. Forward = simulated book return
                after the action. Too early to claim an edge — useful to see the behavior.
              </p>
              <div className="lp-history-table-wrap">
                <table className="lp-history-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Action</th>
                      <th>Day PnL</th>
                      <th>Regime</th>
                      <th>Lock</th>
                      <th>3d later</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Aug 4</td>
                      <td>
                        <span className="lp-pill lp-pill-lock">PROFIT LOCK</span>
                      </td>
                      <td>+$42.80</td>
                      <td>bounce_watch</td>
                      <td>$15</td>
                      <td className="pos">+1.2%</td>
                    </tr>
                    <tr>
                      <td>Aug 5</td>
                      <td>
                        <span className="lp-pill lp-pill-lock">PROFIT LOCK</span>
                      </td>
                      <td>+$40.64</td>
                      <td>bounce_watch</td>
                      <td>$14</td>
                      <td className="pos">+0.4%</td>
                    </tr>
                    <tr>
                      <td>Aug 7</td>
                      <td>
                        <span className="lp-pill lp-pill-lock">PROFIT LOCK</span>
                      </td>
                      <td>+$43.47</td>
                      <td>bounce_watch</td>
                      <td>$15</td>
                      <td className="neg">−1.4%</td>
                    </tr>
                    <tr>
                      <td>Aug 10</td>
                      <td>
                        <span className="lp-pill lp-pill-defense">DEFENSE</span>
                      </td>
                      <td>−$67.34</td>
                      <td>bounce_watch</td>
                      <td>—</td>
                      <td className="neg">−0.7%</td>
                    </tr>
                    <tr>
                      <td>Aug 14</td>
                      <td>
                        <span className="lp-pill lp-pill-hold">CAUTION</span>
                      </td>
                      <td>−$36.98</td>
                      <td>range</td>
                      <td>—</td>
                      <td className="muted">n/a</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="lp-fine lp-center">
                8 HOLD days omitted for brevity. Full replay:{" "}
                <code>python -m src.tools.backtest_action_plan</code>
              </p>
            </div>

            <p className="lp-fine lp-center">
              Thesis: better behavior (discipline, fewer emotional exits) — not
              &quot;guaranteed +X% vs BTC.&quot;{" "}
              <a href="#story">How it started →</a>
            </p>
          </div>
        </section>

        <section className="lp-section lp-section-alt" id="story" aria-labelledby="story-title">
          <div className="lp-wrap lp-story">
            <p className="lp-eyebrow">Why this exists</p>
            <h2 id="story-title">I knew how to buy. I didn&apos;t know when to take profits.</h2>
            <div className="lp-story-body">
              <p>
                Buying was easy. Exits were not. When the book was green I froze. When it was red I
                guessed. I lost money because I had no exit process — no rule for hold, lock, or
                defend on any given day.
              </p>
              <p>
                So I built a tool that answers one question:{" "}
                <strong>“What should I do with my portfolio today?”</strong>
              </p>
              <p>
                LockIn is that answer — a daily decision with reasons — not a prediction
                engine, and not a bot that trades for you.
              </p>
              <p className="lp-mantra">Open the app. Know what to do today.</p>
            </div>
          </div>
        </section>

        <section className="lp-section" id="roadmap" aria-labelledby="roadmap-title">
          <div className="lp-wrap">
            <h2 id="roadmap-title">Honest about what&apos;s ready</h2>
            <p className="lp-lede-sm lp-center">
              Daily decisions work on the founder book. Public proof is still being earned.
            </p>
            <div className="lp-roadmap">
              <article className="lp-card lp-card-done">
                <h3>Working now</h3>
                <ul>
                  <li>Daily action + reasons</li>
                  <li>Profit-lock &amp; risk cushion</li>
                  <li>Demo + early-access list</li>
                </ul>
              </article>
              <article className="lp-card">
                <h3>Next (credibility)</h3>
                <ul>
                  <li>Longer recommendation journal</li>
                  <li>Clearer backtest vs buy&amp;hold / USDT-heavy</li>
                  <li>Read-only Binance for early users</li>
                </ul>
              </article>
            </div>
          </div>
        </section>

        <section className="lp-section lp-cta" id="waitlist" aria-labelledby="waitlist-title">
          <div className="lp-wrap lp-cta-inner">
            <p className="lp-mantra">Open the app. Know what to do today.</p>
            <h2 id="waitlist-title">Want this for your portfolio?</h2>
            <p className="lp-lede">
              Early access is a short list — first ~50 people. You get an email when your spot
              opens (days/weeks, not &quot;someday&quot; vapor). No auto-orders. No Binance keys
              required to join.
            </p>
            <WaitlistForm source="landing_after_demo" />
            <p className="lp-cta-hint lp-center">
              After signup: confirmation in Telegram to the founder + you stay on the list until
              invite.{" "}
              <a href="#demo">Try Demo</a> · <a href="#trust">Why trust this?</a>
            </p>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-wrap lp-footer-inner">
          <span className="lp-logo">LockIn</span>
          <nav aria-label="Footer">
            <a href="#demo">Demo</a>
            <a href="#trust">Why trust</a>
            <a href="#waitlist">Early Access</a>
            <a href="mailto:hello@lockin.app">Contact</a>
          </nav>
          <p className="lp-fine">
            Open the app. Know what to do today. · Advice only. Not financial advice.
          </p>
        </div>
      </footer>
    </>
  );
}
