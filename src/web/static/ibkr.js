async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.error || body.message || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

function usd(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function ibkrActionLabel(action) {
  if (action === "ALERT_SHORT") return "TRIM IDEA";
  if (action === "ALERT") return "DIP IDEA";
  if (action === "WATCH") return "WATCH";
  return action || "—";
}

function signedUsd(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  const s = v > 0 ? "+" : "";
  return `${s}${usd(v)}`;
}

function qtyFmt(n) {
  if (n == null) return "—";
  const v = Number(n);
  if (Math.abs(v) >= 100) return v.toFixed(2);
  if (Math.abs(v) >= 1) return v.toFixed(4);
  return v.toFixed(6);
}

function renderIbkrOverview(overview, portfolio) {
  const meta = document.getElementById("ibkr-meta");
  if (!overview || !overview.available) {
    document.getElementById("ibkr-stat-total").textContent = "—";
    meta.textContent = (overview && overview.message) || "No IBKR data";
    meta.className = "status error";
    return;
  }
  document.getElementById("ibkr-stat-total").textContent = usd(overview.total_usd);
  const daily = overview.daily_pnl_usd;
  const dayEl = document.getElementById("ibkr-today-pnl");
  dayEl.textContent = `Daily P&L: ${daily == null ? "—" : signedUsd(daily)}`;
  dayEl.className = "pnl-line " + (daily == null ? "" : daily >= 0 ? "pos" : "neg");
  const unr = overview.unrealized_pnl_usd;
  const unrEl = document.getElementById("ibkr-unrealized");
  unrEl.textContent = unr == null ? "—" : signedUsd(unr);
  unrEl.className = unr == null ? "" : unr >= 0 ? "pos" : "neg";
  document.getElementById("ibkr-cash").textContent =
    `${usd(overview.cash_usd)} (${overview.cash_pct}%)`;
  document.getElementById("ibkr-count").textContent = overview.positions_count ?? "—";
  meta.textContent = `source: ${overview.source || "—"} · synced ${
    overview.last_synced_at ? overview.last_synced_at.replace("T", " ").slice(0, 19) : "—"
  }`;
  meta.className = "status";

  renderIbkrAction(overview.action_plan || {});
  renderIbkrSwing(overview.swing || {});
  renderIbkrHybrid(overview.hybrid || {});
  fillChartSymbolSelect(portfolio || overview);
  renderIbkrNews(overview);
  renderIbkrRebalance(overview.rebalance || {});
  renderIbkrHoldings(portfolio || {});
}

function pctDip(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return `${(Number(n) * 100).toFixed(1)}%`;
}

function signedPct(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(1)}%`;
}

function renderIbkrHybrid(hybrid) {
  const head = document.getElementById("ibkr-hybrid-headline");
  const rules = document.getElementById("ibkr-hybrid-rules");
  const body = document.getElementById("ibkr-hybrid-body");
  if (!body) return;
  if (head) head.textContent = hybrid.headline || "—";
  if (rules) {
    rules.innerHTML = (hybrid.rules || []).map((t) => `<li>${t}</li>`).join("");
  }
  const rows = hybrid.assets || [];
  body.innerHTML = rows.length
    ? rows
        .map((r) => {
          const grade = r.grade || "neutral";
          const dist20 = signedPct(r.dist_ema20_pct);
          const dist50 = signedPct(r.dist_ema50_pct);
          const cap = `${(r.portfolio_pct ?? "—")}% / ${r.max_pct ?? "—"}%`;
          const over = r.over_cap ? ' class="neg"' : "";
          return `<tr>
            <td><strong>${r.symbol}</strong></td>
            <td><span class="badge mode-${grade}">${r.label || grade}</span></td>
            <td>${r.horizon || "—"}</td>
            <td${over}>${cap}</td>
            <td class="${(r.dist_ema20_pct || 0) >= 0 ? "pos" : "neg"}">${dist20}</td>
            <td class="${(r.dist_ema50_pct || 0) >= 0 ? "pos" : "neg"}">${dist50}</td>
            <td title="${(r.why || "") + " · " + (r.signal_note || "")}">${r.signal || "—"}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="7" style="color:var(--muted)">Немає холдингів</td></tr>`;
}

let ibkrPriceChart = null;

function fillChartSymbolSelect(portfolio) {
  const sel = document.getElementById("ibkr-chart-symbol");
  if (!sel) return;
  const holdings = (portfolio && portfolio.holdings) || [];
  const symbols = holdings.map((h) => h.symbol).filter(Boolean);
  const prev = sel.value;
  sel.innerHTML = symbols.map((s) => `<option value="${s}">${s}</option>`).join("");
  if (prev && symbols.includes(prev)) sel.value = prev;
  else if (symbols.includes("CIBR")) sel.value = "CIBR";
  else if (symbols.includes("QTUM")) sel.value = "QTUM";
  else if (symbols[0]) sel.value = symbols[0];
}

async function loadIbkrChart() {
  const sel = document.getElementById("ibkr-chart-symbol");
  const rangeEl = document.getElementById("ibkr-chart-range");
  const status = document.getElementById("ibkr-chart-status");
  const canvas = document.getElementById("ibkr-price-chart");
  if (!sel || !canvas) return;
  const symbol = sel.value;
  const range = (rangeEl && rangeEl.value) || "6mo";
  if (!symbol) {
    if (status) status.textContent = "Немає символу";
    return;
  }
  if (status) {
    status.className = "status";
    status.textContent = `Loading ${symbol}…`;
  }
  try {
    const data = await fetchJson(
      `/api/ibkr/chart/${encodeURIComponent(symbol)}?range=${encodeURIComponent(range)}&interval=1d`
    );
    if (!data.available || !(data.bars || []).length) {
      if (status) {
        status.className = "status error";
        status.textContent = data.error || "No chart data";
      }
      return;
    }
    const labels = data.bars.map((b) => (b.t || "").slice(0, 10));
    const closes = data.bars.map((b) => b.c);
    const ema20 = data.ema20 || [];
    const ema50 = data.ema50 || [];
    const ctx = canvas.getContext("2d");
    if (ibkrPriceChart) ibkrPriceChart.destroy();
    ibkrPriceChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: `${symbol} close`,
            data: closes,
            borderColor: "#7dd3fc",
            backgroundColor: "transparent",
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.05,
          },
          {
            label: "EMA20",
            data: ema20,
            borderColor: "#fbbf24",
            backgroundColor: "transparent",
            borderWidth: 1.2,
            pointRadius: 0,
            spanGaps: true,
          },
          {
            label: "EMA50",
            data: ema50,
            borderColor: "#f472b6",
            backgroundColor: "transparent",
            borderWidth: 1.2,
            pointRadius: 0,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#94a3b8", boxWidth: 12 } },
        },
        scales: {
          x: {
            ticks: { color: "#64748b", maxTicksLimit: 8 },
            grid: { color: "#1e293b" },
          },
          y: {
            ticks: { color: "#64748b" },
            grid: { color: "#1e293b" },
          },
        },
      },
    });
    const d20 = data.dist_ema20_pct != null ? `${signedPct(data.dist_ema20_pct)} vs EMA20` : "";
    const d50 = data.dist_ema50_pct != null ? `${signedPct(data.dist_ema50_pct)} vs EMA50` : "";
    if (status) {
      status.className = "status";
      status.textContent = `${symbol} last ${usd(data.last)} · ${d20} · ${d50}`;
    }
  } catch (err) {
    if (status) {
      status.className = "status error";
      status.textContent = `Chart failed: ${err.message}`;
    }
  }
}

function renderIbkrNews(overview) {
  const alertsBody = document.getElementById("ibkr-alerts-body");
  const newsBody = document.getElementById("ibkr-news-body");
  const status = document.getElementById("ibkr-news-status");
  if (!alertsBody || !newsBody) return;

  const meta = (overview && overview.news_meta) || {};
  const alerts = (overview && overview.alerts) || [];
  const news = (overview && overview.news) || [];

  if (status && !window.__ibkrNewsFlash) {
    if (meta.error) {
      status.className = "status error";
      status.textContent = meta.error;
    } else if (meta.last_run) {
      status.className = "status";
      const st = meta.stats || {};
      status.textContent =
        `Last news: ${String(meta.last_run).replace("T", " ").slice(0, 19)}` +
        ` · headlines ${st.news_count ?? news.length}` +
        ` · alerts ${st.alert_count ?? alerts.length}`;
    } else {
      status.className = "status";
      status.textContent = "Натисни Refresh news (Yahoo, ~15–40с)";
    }
  }

  alertsBody.innerHTML = alerts.length
    ? alerts
        .map((a) => {
          const t = (a.timestamp || "").replace("T", " ").slice(0, 19);
          const title = a.news_url
            ? `<a href="${a.news_url}" target="_blank" rel="noopener">${a.news_title || "—"}</a>`
            : a.news_title || "—";
          return `<tr>
            <td>${t || "—"}</td>
            <td><span class="badge ${a.action || ""}">${ibkrActionLabel(a.action)}</span></td>
            <td><strong>${a.symbol || "—"}</strong></td>
            <td>${pctDip(a.dip_pct)}</td>
            <td>${a.suggested_size_usdt ? usd(a.suggested_size_usdt) : "—"}</td>
            <td>${title}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="6" style="color:var(--muted)">Немає ALERT / WATCH — Refresh news або чекай сетап</td></tr>`;

  newsBody.innerHTML = news.length
    ? news
        .slice(0, 25)
        .map((n) => {
          const title = n.url
            ? `<a href="${n.url}" target="_blank" rel="noopener">${n.title || "—"}</a>`
            : n.title || "—";
          const assets = (n.assets || []).join(", ") || "—";
          return `<tr>
            <td><span class="badge">${n.sentiment || "—"}</span> ${n.confidence || ""}</td>
            <td>${assets}</td>
            <td>${n.source || "—"}</td>
            <td>${title}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="4" style="color:var(--muted)">Ще немає новин — натисни Refresh news</td></tr>`;
}

function renderIbkrSwing(swing) {
  const head = document.getElementById("ibkr-swing-headline");
  const rules = document.getElementById("ibkr-swing-rules");
  const buysBody = document.getElementById("ibkr-swing-buys");
  const sellsBody = document.getElementById("ibkr-swing-sells");
  if (!head) return;
  head.textContent = swing.headline || "—";
  rules.innerHTML = (swing.rules || []).map((t) => `<li>${t}</li>`).join("");
  const buys = swing.buys || [];
  const sells = swing.sells || [];
  buysBody.innerHTML = buys.length
    ? buys
        .map(
          (b) => `<tr>
        <td><strong>${b.symbol}</strong></td>
        <td class="neg">${b.unrealized_pct.toFixed(1)}%</td>
        <td class="pos">+${usd(b.amount_usd)}</td>
        <td>${b.note || "—"}</td>
      </tr>`
        )
        .join("")
    : `<tr><td colspan="4" style="color:var(--muted)">${
        swing.can_buy
          ? "Немає глибоких просадок vs cost зараз"
          : "Спочатку підніми cash (trim), потім лови dips"
      }</td></tr>`;
  sellsBody.innerHTML = sells.length
    ? sells
        .map(
          (s) => `<tr>
        <td><strong>${s.symbol}</strong></td>
        <td class="pos">+${s.unrealized_pct.toFixed(1)}%</td>
        <td class="neg">−${usd(s.amount_usd)}</td>
        <td>${usd(s.keep_usd)}</td>
      </tr>`
        )
        .join("")
    : `<tr><td colspan="4" style="color:var(--muted)">Немає сильних +25% vs cost для великого trim</td></tr>`;
}

function renderIbkrAction(plan) {
  const card = document.getElementById("ibkr-action-card");
  const badge = document.getElementById("ibkr-action-badge");
  const headline = document.getElementById("ibkr-action-headline");
  const checklist = document.getElementById("ibkr-action-checklist");
  const sellsBody = document.getElementById("ibkr-sells-body");
  const sellsWrap = document.getElementById("ibkr-sells-wrap");
  const note = document.getElementById("ibkr-action-note");
  const rules = document.getElementById("ibkr-action-rules");
  if (!badge || !headline) return;
  const mode = plan.mode || "hold";
  if (card) card.dataset.mode = mode;
  badge.textContent = mode;
  badge.className = `badge mode-${mode}`;
  headline.textContent = plan.headline || "Hold · нічого обов’язкового";
  if (checklist) {
    const extras = (plan.checklist || []).filter(Boolean);
    checklist.innerHTML = extras.length
      ? extras.map((t) => `<li>${t}</li>`).join("")
      : "";
  }
  const actions = plan.actions || [];
  if (sellsWrap && sellsBody) {
    if (!actions.length) {
      sellsWrap.style.display = "none";
      sellsBody.innerHTML = "";
    } else {
      sellsWrap.style.display = "";
      sellsBody.innerHTML = actions
        .map(
          (a) => `
      <tr>
        <td><strong>${a.symbol}</strong></td>
        <td class="neg">−${usd(a.sell_usd)}</td>
        <td>${a.pct_of_bag}%</td>
        <td>${a.reason || "—"}</td>
      </tr>`
        )
        .join("");
    }
  }
  if (note) note.textContent = plan.note || "";
  if (rules && plan.rules) {
    const r = plan.rules;
    rules.textContent = [r.profit_lock, r.defense, r.structure].filter(Boolean).join(" · ");
  }
}

function renderIbkrRebalance(rebalance) {
  const policy = document.getElementById("ibkr-rebalance-policy");
  const body = document.getElementById("ibkr-rebalance-body");
  const sleeveBody = document.getElementById("ibkr-sleeve-body");
  if (policy && rebalance.policy) policy.textContent = rebalance.policy;
  const rows = [...(rebalance.actionable || []), ...(rebalance.minor || [])];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7" style="color:var(--muted)">Немає термінових дій.</td></tr>`;
  } else {
    body.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td><strong>${r.asset}</strong></td>
        <td><span class="badge ${r.action}">${r.action}</span></td>
        <td>${r.current_pct}%</td>
        <td>${r.target_pct}%</td>
        <td class="${r.deviation_pct >= 0 ? "pos" : "neg"}">${r.deviation_pct > 0 ? "+" : ""}${r.deviation_pct}</td>
        <td>${r.amount_usd > 0 ? "+" : ""}${usd(r.amount_usd)}</td>
        <td>${r.note || "—"}</td>
      </tr>`
      )
      .join("");
  }
  const sleeves = rebalance.allocation || [];
  sleeveBody.innerHTML = sleeves.length
    ? sleeves
        .map((r) => {
          const gapCls = Math.abs(r.gap_pct) < 1 ? "" : r.gap_pct > 0 ? "pos" : "neg";
          return `<tr>
            <td><strong>${r.sleeve}</strong></td>
            <td>${r.current_pct}%</td>
            <td>${r.target_pct}%</td>
            <td class="${gapCls}">${r.gap_pct > 0 ? "+" : ""}${r.gap_pct}%</td>
            <td>${usd(r.value_usd)}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="5" style="color:var(--muted)">—</td></tr>`;
}

function holdingRole(h) {
  const sym = (h.symbol || "").toUpperCase();
  const tag = (h.tag || "").toLowerCase();
  const mv = Number(h.market_value || 0);
  if (sym === "CSPX" || sym === "CIBR") return { id: "build", label: "build" };
  if (["IONQ", "QBTS", "ROKT", "SPCX", "EVX", "WTAI"].includes(sym)) {
    return { id: "satellite", label: "satellite" };
  }
  if (tag === "quantum" || tag === "spec_etf" || tag === "ai_etf") {
    return { id: "satellite", label: "satellite" };
  }
  if (mv > 0 && mv < 8) return { id: "dust", label: "dust" };
  if (tag === "core" || tag === "semi" || ["AAPL", "AMZN", "NVDA", "GOOG", "NFLX", "MU"].includes(sym)) {
    return { id: "keep", label: "keep" };
  }
  if (tag === "theme_etf" || tag === "core_etf") return { id: "build", label: "build" };
  return { id: "keep", label: "keep" };
}

function renderIbkrHoldings(portfolio) {
  const body = document.getElementById("ibkr-holdings-body");
  const rows = portfolio.holdings || [];
  const hint = document.getElementById("ibkr-lines-hint");
  if (hint) {
    const n = rows.length;
    hint.textContent = n > 8 ? `(ціль ≤8 · зараз багато)` : n ? `(ок)` : "";
  }
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5" style="color:var(--muted)">No positions</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((h) => {
      const role = holdingRole(h);
      const u = Number(h.unrealized_pnl_pct);
      const uCls = u >= 0 ? "pos" : "neg";
      const uTxt = Number.isFinite(u) ? `${u > 0 ? "+" : ""}${u.toFixed(1)}%` : "—";
      return `<tr>
        <td><strong>${h.symbol}</strong></td>
        <td class="role-${role.id}">${role.label}</td>
        <td>${usd(h.market_value)}</td>
        <td>${h.pct}%</td>
        <td class="${uCls}">${uTxt}</td>
      </tr>`;
    })
    .join("");
}

async function refreshIbkr() {
  const status = document.getElementById("ibkr-last-run");
  try {
    const [portfolio, overview] = await Promise.all([
      fetchJson("/api/ibkr/portfolio"),
      fetchJson("/api/ibkr/overview"),
    ]);
    renderIbkrOverview(overview, portfolio);
    status.className = "status";
    status.textContent = overview.last_synced_at
      ? `Snapshot: ${overview.last_synced_at.replace("T", " ").slice(0, 19)}`
      : "IBKR loaded";
  } catch (err) {
    status.className = "status error";
    status.textContent = `IBKR failed: ${err.message}`;
  }
}

document.getElementById("ibkr-reload-btn").addEventListener("click", () => refreshIbkr());

async function refreshFlexStatus() {
  const hint = document.getElementById("ibkr-flex-hint");
  const badge = document.getElementById("conn-badge");
  const btn = document.getElementById("ibkr-flex-btn");
  try {
    const st = await fetchJson("/api/ibkr/flex-status");
    if (hint) {
      hint.textContent = st.hint || "";
      hint.className = st.configured ? "hint" : "hint";
    }
    if (badge) {
      badge.textContent = st.configured
        ? `IBKR Flex ready${st.account_id_hint ? " " + st.account_id_hint : ""}`
        : "IBKR snapshot (Flex not configured)";
    }
    if (btn) btn.disabled = false;
  } catch (_) {
    if (hint) hint.textContent = "Flex status unavailable";
  }
}

document.getElementById("ibkr-flex-btn")?.addEventListener("click", async () => {
  const btn = document.getElementById("ibkr-flex-btn");
  const status = document.getElementById("ibkr-last-run");
  if (btn) btn.disabled = true;
  if (status) {
    status.className = "status";
    status.textContent = "Flex sync… (IBKR може думати 10–60с)";
  }
  try {
    const res = await fetchJson("/api/ibkr/flex-sync", { method: "POST" });
    if (status) {
      status.className = "status";
      status.textContent = res.message || "Flex sync ok";
    }
    if (res.overview && res.portfolio) {
      renderIbkrOverview(res.overview, res.portfolio);
      setTimeout(() => loadIbkrChart(), 300);
    } else {
      await refreshIbkr();
    }
  } catch (err) {
    if (status) {
      status.className = "status error";
      status.textContent = `Flex sync failed: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
    refreshFlexStatus();
  }
});

document.getElementById("ibkr-reseeds-btn").addEventListener("click", async () => {
  if (!confirm("Reset IBKR snapshot to the screenshot seed?")) return;
  await fetchJson("/api/ibkr/reload-seed", { method: "POST" });
  await refreshIbkr();
});

document.getElementById("ibkr-hybrid-btn")?.addEventListener("click", async () => {
  const btn = document.getElementById("ibkr-hybrid-btn");
  const status = document.getElementById("ibkr-hybrid-status");
  if (btn) btn.disabled = true;
  if (status) {
    status.className = "status";
    status.textContent = "Yahoo daily + EMA20/50… (~20–40с)";
  }
  try {
    const res = await fetchJson("/api/ibkr/hybrid-refresh", { method: "POST" });
    renderIbkrHybrid(res.hybrid || {});
    if (status) {
      status.className = "status";
      const n = ((res.hybrid || {}).assets || []).length;
      const pb = ((res.hybrid || {}).pullback_candidates || []).join(", ") || "—";
      status.textContent = `EMA ok · ${n} names · pullback: ${pb}`;
    }
  } catch (err) {
    if (status) {
      status.className = "status error";
      status.textContent = `Hybrid refresh failed: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("ibkr-chart-btn")?.addEventListener("click", () => loadIbkrChart());
document.getElementById("ibkr-chart-symbol")?.addEventListener("change", () => loadIbkrChart());
document.getElementById("ibkr-chart-range")?.addEventListener("change", () => loadIbkrChart());

document.getElementById("ibkr-news-btn")?.addEventListener("click", async () => {
  const btn = document.getElementById("ibkr-news-btn");
  const status = document.getElementById("ibkr-news-status");
  if (btn) btn.disabled = true;
  if (status) {
    status.className = "status";
    status.textContent = "Fetching Yahoo news + charts… (15–40s)";
    window.__ibkrNewsFlash = status.textContent;
  }
  try {
    const res = await fetchJson("/api/ibkr/news-refresh", { method: "POST" });
    const meta = res.news_meta || {};
    const msg = meta.error
      ? `News error: ${meta.error}`
      : `News ok · headlines ${(res.news || []).length} · alerts ${(res.alerts || []).length}`;
    window.__ibkrNewsFlash = msg;
    if (status) {
      status.textContent = msg;
      status.className = meta.error ? "status error" : "status";
    }
    if (res.overview) {
      const portfolio = await fetchJson("/api/ibkr/portfolio");
      renderIbkrOverview(res.overview, portfolio);
    } else {
      await refreshIbkr();
    }
    if (window.__ibkrNewsFlash && status) {
      status.textContent = window.__ibkrNewsFlash;
      setTimeout(() => { window.__ibkrNewsFlash = null; }, 8000);
    }
  } catch (err) {
    if (status) {
      status.className = "status error";
      status.textContent = `News refresh failed: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
});

refreshFlexStatus();
refreshIbkr();
setInterval(refreshIbkr, 60000);
