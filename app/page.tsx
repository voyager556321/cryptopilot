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
              <p className="lp-eyebrow">Not a trading bot · daily decisions</p>
              <h1 id="hero-title">Know what to do with your crypto portfolio today.</h1>
              <p className="lp-lede">
                Advice only — hold, lock profit, defend, or rebalance — with reasons you can
                check. Not signals. Not auto-trading. A process for exits when emotion takes over.
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
                <a href="#trust">Real locks from the founder&apos;s book — no fake returns.</a>
              </p>
            </div>
          </div>
        </section>

        <DemoPortfolio />

        <section className="lp-section" id="before-after" aria-labelledby="ba-title">
          <div className="lp-wrap">
            <h2 id="ba-title" className="lp-center">
              Same market. Different process.
            </h2>
            <p className="lp-lede-sm lp-center">Open the app. Know what to do today.</p>
            <div className="lp-ba">
              <article className="lp-ba-card lp-ba-before">
                <h3>Before CryptoPilot</h3>
                <p className="lp-ba-stat">BTC +8%</p>
                <ul className="lp-ba-chaos">
                  <li>Should I sell?</li>
                  <li>Should I hold?</li>
                  <li>Should I buy more?</li>
                  <li>Should I wait?</li>
                </ul>
                <p className="lp-ba-verdict">
                  Too many signals.
                  <br />
                  No process.
                </p>
              </article>
              <div className="lp-ba-arrow" aria-hidden="true">
                →
              </div>
              <article className="lp-ba-card lp-ba-after">
                <h3>After CryptoPilot</h3>
                <div className="lp-ba-rec">
                  <span className="lp-product-day">TODAY</span>
                  <p className="lp-product-action lp-product-action-sm">ACTION: HOLD</p>
                  <p className="lp-product-reasons-label">Reasons</p>
                  <ul className="lp-product-reasons">
                    <li>BTC neutral</li>
                    <li>USDT below target</li>
                    <li>No strong signal</li>
                    <li>Stick to the plan</li>
                  </ul>
                </div>
                <p className="lp-ba-verdict lp-ba-verdict-ok">
                  One decision.
                  <br />
                  Clear reasons.
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
              Here is what exists today. No invented performance.
            </p>

            <div className="lp-trust-grid">
              <article className="lp-trust-card">
                <h3>Not smarter than you</h3>
                <p>
                  The engine does not predict the top. It applies fixed rules: green day →
                  consider profit lock; deep red → defense; otherwise hold. You stay in control —
                  advice only, no auto-orders.
                </p>
              </article>
              <article className="lp-trust-card">
                <h3>Not a trading bot</h3>
                <p>
                  Other products named &quot;CryptoPilot&quot; sell signals or automation. This one
                  answers one question: what should I do with <em>my</em> portfolio{" "}
                  <em>today</em>? If you want a bot that trades for you — this isn&apos;t it.
                </p>
              </article>
              <article className="lp-trust-card">
                <h3>Founder&apos;s live book</h3>
                <p>
                  Running on a real spot portfolio first. Take-profit days logged into USDT:
                  Aug 4 (~$27), Aug 7 (~$20), Aug 8 (~$7), Aug 9 (~$5) — about{" "}
                  <strong>$59 locked</strong> total. Small. Real. Not marketed alpha.
                </p>
              </article>
              <article className="lp-trust-card">
                <h3>Early history replay</h3>
                <p>
                  Same production <code>build_action_plan()</code> on 13 days of sleeve history
                  (Aug 2–14). Simulated locks ~$44. Drawdown almost tied with buy&amp;hold —
                  <strong> too short to claim an edge</strong>. We publish that on purpose.
                  Longer tape → clearer behavior proof.
                </p>
              </article>
            </div>

            <div className="lp-proof lp-proof-tight">
              <article className="lp-proof-item">
                <p className="lp-proof-num">~$59</p>
                <p className="lp-proof-label">USDT locked on 4 take-profit days</p>
              </article>
              <article className="lp-proof-item">
                <p className="lp-proof-num">2,900+</p>
                <p className="lp-proof-label">Portfolio snapshots in the founder tape</p>
              </article>
              <article className="lp-proof-item">
                <p className="lp-proof-num">13 days</p>
                <p className="lp-proof-label">Backtest window — early, not conclusive</p>
              </article>
              <article className="lp-proof-item">
                <p className="lp-proof-num">Rules</p>
                <p className="lp-proof-label">Deterministic · no LLM as the brain</p>
              </article>
            </div>

            <p className="lp-fine lp-center">
              Thesis: better behavior (discipline, smaller emotional mistakes) — not
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
                CryptoPilot is that answer — a daily decision with reasons — not a prediction
                engine, and not a bot that trades for you. If another &quot;CryptoPilot&quot; is
                selling signals or auto-trades, that is a different product.
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
          <span className="lp-logo">CryptoPilot</span>
          <nav aria-label="Footer">
            <a href="#demo">Demo</a>
            <a href="#trust">Why trust</a>
            <a href="#waitlist">Early Access</a>
            <a href="mailto:hello@cryptopilot.app">Contact</a>
          </nav>
          <p className="lp-fine">
            Open the app. Know what to do today. · Advice only. Not financial advice.
          </p>
        </div>
      </footer>
    </>
  );
}
