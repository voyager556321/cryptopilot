const pct = (v) => {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(2)}%`;
};

const money = (v) => {
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
};

const usd = (v) => `$${money(v)}`;

const qtyFmt = (v) => {
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  if (n >= 100) return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (n >= 1) return n.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return n.toLocaleString("en-US", { maximumFractionDigits: 8 });
};

const signedUsd = (v) => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${usd(n)}`;
};

const signedPct = (v) => {
  if (v === null || v === undefined) return "";
  const n = Number(v);
  if (Number.isNaN(n)) return "";
  const sign = n > 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(2)}%`;
};

let equityChart = null;

async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.message || body.error || JSON.stringify(body);
    } catch (_) {
      detail = res.statusText;
    }
    throw new Error(`${url} → ${res.status}${detail ? `: ${detail}` : ""}`);
  }
  return res.json();
}

function renderConfig(cfg) {
  const root = document.getElementById("config-grid");
  const badge = document.getElementById("conn-badge");
  if (!cfg) {
    root.innerHTML = `<p class="status error">Config unavailable</p>`;
    return;
  }

  badge.textContent = cfg.connected_label || "—";
  badge.className = "conn" + (cfg.api_keys_present ? " ok" : " bad");

  const rows = [
    ["Exchange", cfg.exchange],
    ["API key", cfg.api_key],
    ["Strategy mode", cfg.strategy_mode],
    ["Auto paper", String(cfg.auto_paper)],
    ["Paper bank", cfg.paper_bank_usdt],
    ["Bear alerts", String(cfg.enable_bear_alerts)],
    ["Symbols", (cfg.symbols || []).join(", ")],
    ["Bank USDT", cfg.bank_usdt],
    ["Risk / alert", cfg.risk_per_alert_pct != null ? pct(cfg.risk_per_alert_pct) : "—"],
    ["Poll interval", cfg.poll_interval_seconds != null ? `${cfg.poll_interval_seconds}s` : "—"],
    ["News sources", (cfg.news_sources || []).join(", ")],
    ["Dip range", cfg.dip_min_pct != null ? `${pct(cfg.dip_min_pct)} – ${pct(cfg.dip_max_pct)}` : "—"],
    ["Mode", cfg.mode],
    ["Dry run", String(cfg.dry_run)],
  ];

  root.innerHTML = rows
    .map(
      ([k, v]) => `
    <div class="config-item">
      <div class="k">${k}</div>
      <div class="v">${v ?? "—"}</div>
    </div>`
    )
    .join("");
}

function renderAccounts(accounts) {
  const body = document.getElementById("accounts-body");
  if (!accounts || !accounts.length) {
    body.innerHTML = `<tr><td colspan="4" style="color:var(--muted)">No exchange keys in .env</td></tr>`;
    return;
  }
  body.innerHTML = accounts
    .map(
      (a) => `
    <tr>
      <td><strong>${a.name}</strong></td>
      <td><span class="badge">${a.source}</span></td>
      <td>${a.api_key || "••••"}</td>
      <td>${a.last_synced_at ? a.last_synced_at.replace("T", " ").slice(0, 19) : "—"}</td>
    </tr>`
    )
    .join("");
}

function renderMarkets(markets) {
  const root = document.getElementById("markets");
  const symbols = Object.keys(markets || {});
  document.getElementById("stat-markets").textContent = String(symbols.length || 0);

  if (!symbols.length) {
    root.innerHTML = `<div class="card"><h3>Markets</h3><p class="status">No data yet</p></div>`;
    return;
  }

  root.innerHTML = symbols
    .map((sym) => {
      const m = markets[sym];
      const ch = m.change_24h_pct;
      const cls = ch == null ? "" : ch >= 0 ? "pos" : "neg";
      return `
      <div class="card">
        <h3>${sym}</h3>
        <div class="price">${usd(m.price)}</div>
        <div class="row">
          <span class="${cls}">24h ${ch == null ? "—" : pct(ch)}</span>
          <span>dip ${pct(m.dip_pct)}</span>
          <span>vol× ${Number(m.volume_ratio || 0).toFixed(2)}</span>
        </div>
      </div>`;
    })
    .join("");
}

function renderAlerts(signals) {
  const body = document.getElementById("alerts-body");
  const alerts = (signals || []).filter((s) =>
    ["ALERT", "ALERT_SHORT", "WATCH"].includes(s.action)
  ).slice(0, 40);
  document.getElementById("stat-alerts").textContent = String(alerts.length);

  if (!alerts.length) {
    body.innerHTML = `<tr><td colspan="7" style="color:var(--muted)">No alerts yet — bull dip, bear sell, or WATCH</td></tr>`;
    return;
  }

  body.innerHTML = alerts
    .map(
      (s) => `
    <tr>
      <td>${(s.timestamp || "").replace("T", " ").slice(0, 19)}</td>
      <td><strong>${s.symbol}</strong> <span class="badge ${s.action}">${s.action}</span></td>
      <td>${usd(s.price)}</td>
      <td>${pct(s.dip_pct)}</td>
      <td>${usd(s.suggested_size_usdt)}</td>
      <td><a href="${s.news_url}" target="_blank" rel="noopener">${s.news_title || "link"}</a></td>
      <td><span class="badge ${s.sentiment || "unclear"}">${s.sentiment || "—"}</span></td>
    </tr>`
    )
    .join("");
}

function renderPaper(paper) {
  const body = document.getElementById("paper-body");
  if (!paper) {
    document.getElementById("stat-paper-pnl").textContent = "—";
    document.getElementById("stat-paper-counts").textContent = "—";
    document.getElementById("stat-paper-wl").textContent = "—";
    document.getElementById("stat-paper-by").textContent = "—";
    body.innerHTML = `<tr><td colspan="9" style="color:var(--muted)">No paper data</td></tr>`;
    return;
  }

  const pnlEl = document.getElementById("stat-paper-pnl");
  pnlEl.textContent = signedUsd(paper.total_pnl_usdt);
  pnlEl.className = "value " + (paper.total_pnl_usdt >= 0 ? "pos" : "neg");
  document.getElementById("paper-meta").textContent =
    `Realized ${signedUsd(paper.realized_pnl_usdt)} · Unrealized ${signedUsd(paper.unrealized_pnl_usdt)}`;
  document.getElementById("stat-paper-counts").textContent =
    `${paper.open_count} / ${paper.closed_count}`;
  document.getElementById("stat-paper-wl").textContent =
    `${paper.wins} / ${paper.losses}`;
  const by = paper.by_strategy || {};
  document.getElementById("stat-paper-by").textContent =
    Object.keys(by).length
      ? Object.entries(by).map(([k, v]) => `${k}: ${signedUsd(v)}`).join(" · ")
      : "—";

  const rows = [...(paper.open || []), ...(paper.closed || []).slice(0, 30)];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="9" style="color:var(--muted)">No paper trades yet — after Sync they appear on ALERT / rebalance drift</td></tr>`;
    return;
  }

  body.innerHTML = rows
    .map((p) => {
      const pnl = p.status === "closed" ? p.realized_pnl_usdt : p.unrealized_pnl_usdt;
      const cls = pnl >= 0 ? "pos" : "neg";
      return `
      <tr>
        <td>${(p.opened_at || "").replace("T", " ").slice(0, 19)}</td>
        <td><span class="badge">${p.strategy}</span></td>
        <td><span class="badge ${p.side}">${p.side}</span></td>
        <td><strong>${p.symbol}</strong></td>
        <td>${usd(p.entry_price)}</td>
        <td>${usd(p.mark_price || p.exit_price)}</td>
        <td>${usd(p.size_usdt)}</td>
        <td class="${cls}">${signedUsd(pnl)} ${p.close_reason ? `(${p.close_reason})` : ""}</td>
        <td>${p.status}</td>
      </tr>`;
    })
    .join("");
}

function setModeButtons(active) {
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === active);
  });
}

function renderSignals(signals) {
  const body = document.getElementById("signals-body");
  const rows = (signals || []).slice(0, 50);

  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6" style="color:var(--muted)">No signals logged</td></tr>`;
    return;
  }

  body.innerHTML = rows
    .map(
      (s) => `
    <tr>
      <td>${(s.timestamp || "").replace("T", " ").slice(0, 19)}</td>
      <td><strong>${s.symbol}</strong></td>
      <td><span class="badge ${s.action}">${s.action}</span></td>
      <td>${s.skip_reason || "—"}</td>
      <td>${pct(s.dip_pct)}</td>
      <td>${Number(s.volume_ratio || 0).toFixed(2)}</td>
    </tr>`
    )
    .join("");
}

function renderNews(news) {
  const list = document.getElementById("news-list");
  if (!news || !news.length) {
    list.innerHTML = `<li class="status">No news yet</li>`;
    return;
  }

  list.innerHTML = news
    .slice(0, 40)
    .map(
      (n) => `
    <li>
      <div class="meta-line">
        <span class="badge ${n.sentiment}">${n.sentiment}</span>
        <span class="badge">${n.source || "news"}</span>
        <span>${(n.assets || []).join(", ") || "—"}</span>
        <span>${n.confidence || ""}</span>
      </div>
      <a href="${n.url}" target="_blank" rel="noopener">${n.title}</a>
    </li>`
    )
    .join("");
}

function holdingsFromPortfolio(data) {
  if (Array.isArray(data.holdings) && data.holdings.length) return data.holdings;
  return Object.entries(data.assets || {}).map(([symbol, info]) => ({
    symbol,
    quantity: info.quantity,
    price_usdt: info.price_usdt,
    value_usdt: info.value_usdt,
    pct: info.pct,
    asset_class: symbol === "USDT" || symbol === "USDC" ? "stable" : "crypto",
  }));
}

function renderPnlLine(el, label, delta) {
  if (!delta || delta.abs == null) {
    el.textContent = `${label}: — (need a few syncs for history)`;
    el.className = "pnl-line";
    return;
  }
  const cls = delta.abs >= 0 ? "pos" : "neg";
  el.className = `pnl-line ${cls}`;
  el.textContent = `${label}: ${signedUsd(delta.abs)} (${signedPct(delta.pct)})`;
}

function renderEquityChart(series) {
  const ctx = document.getElementById("equity-chart");
  if (!ctx || typeof Chart === "undefined") return;
  const labels = (series || []).map((p) => (p.timestamp || "").replace("T", " ").slice(5, 16));
  const data = (series || []).map((p) => p.total_usdt);
  if (equityChart) equityChart.destroy();
  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          data,
          borderColor: "#e6b84d",
          backgroundColor: "rgba(230, 184, 77, 0.12)",
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: {
          ticks: { color: "#9aa0a6", callback: (v) => `$${v}` },
          grid: { color: "#2a2f3d66" },
        },
      },
    },
  });
}

function renderOverview(overview, portfolio) {
  const meta = document.getElementById("portfolio-meta");
  const history = (overview && overview.history) || {};

  if (!overview || !overview.available) {
    document.getElementById("stat-portfolio").textContent = "—";
    document.getElementById("stat-24h").textContent = "—";
    document.getElementById("stat-7d").textContent = "—";
    document.getElementById("stat-btc-eth").textContent = "—";
    document.getElementById("stat-mix").textContent = "—";
    document.getElementById("today-pnl").textContent = "Today's PnL: —";
    meta.textContent = (overview && overview.message) || "Portfolio unavailable";
    meta.className = "status error";
    renderActionPlan(overview && overview.action_plan ? overview.action_plan : {
      mode: "hold",
      headline: "Connect API keys to see the lock / defense plan.",
      checklist: [],
      actions: [],
    });
    renderLockedPeriods(overview && overview.profit_lock ? overview.profit_lock : {});
    return;
  }

  document.getElementById("stat-portfolio").textContent = usd(overview.total_usdt);
  document.getElementById("stat-btc-eth").textContent = `${overview.btc_eth_pct}%`;
  document.getElementById("stat-mix").textContent = `${overview.stable_pct}% / ${overview.alts_pct}%`;

  const d24 = history.pnl_24h || {};
  const d7 = history.pnl_7d || {};
  const el24 = document.getElementById("stat-24h");
  const el7 = document.getElementById("stat-7d");
  el24.textContent = d24.abs == null ? "—" : `${signedUsd(d24.abs)}`;
  el24.className = "value " + (d24.abs == null ? "" : d24.abs >= 0 ? "pos" : "neg");
  el7.textContent = d7.abs == null ? "—" : `${signedUsd(d7.abs)}`;
  el7.className = "value " + (d7.abs == null ? "" : d7.abs >= 0 ? "pos" : "neg");

  renderPnlLine(document.getElementById("today-pnl"), "Today's PnL", history.today_pnl);
  renderEquityChart(history.series || []);

  const synced = overview.last_synced_at
    ? ` · synced ${overview.last_synced_at.replace("T", " ").slice(0, 19)}`
    : "";
  const points = history.points != null ? ` · history points: ${history.points}` : "";
  meta.textContent = `${history.note || "Mark-to-market vs app snapshots"}${synced}${points}`;
  meta.className = "status";

  renderMarketCycle(overview.market_cycle || {});
  renderActionPlan(overview.action_plan || {});
  renderLockedPeriods(overview.profit_lock || {});
  renderRebalance(overview.rebalance || {});
  renderHoldings(portfolio, overview.rebalance || {});
  renderAllocation(overview.rebalance || {});
}

function renderLockedPeriods(lock) {
  const periods = (lock && lock.periods) || {};
  const map = [
    ["lock-period-day", periods.day],
    ["lock-period-week", periods.week],
    ["lock-period-month", periods.month],
    ["lock-period-quarter", periods.quarter],
  ];
  for (const [id, row] of map) {
    const el = document.getElementById(id);
    if (!el) continue;
    const amt = row && row.locked_usdt != null ? Number(row.locked_usdt) : null;
    if (amt == null) {
      el.textContent = "—";
      el.className = "value";
      continue;
    }
    el.textContent = usd(amt);
    el.className = "value " + (amt > 0 ? "pos" : amt < 0 ? "neg" : "");
  }
}

function renderMarketCycle(cycle) {
  const card = document.getElementById("cycle-card");
  const badge = document.getElementById("cycle-mode-badge");
  const headline = document.getElementById("cycle-headline");
  const checklist = document.getElementById("cycle-checklist");
  const levelsEl = document.getElementById("cycle-levels");
  const note = document.getElementById("cycle-note");
  if (!card || !cycle) return;

  const mode = cycle.mode || "unknown";
  card.dataset.mode = mode;
  badge.textContent = mode;
  badge.className = `badge mode-${mode}`;
  headline.textContent = cycle.headline || "—";
  const items = cycle.checklist || [];
  checklist.innerHTML = items.length
    ? items.map((t) => `<li>${t}</li>`).join("")
    : "<li>—</li>";

  const lv = cycle.levels || {};
  if (lv.spot) {
    const buys = (lv.limit_buy_btc || [])
      .map((x) => `${x.label} ~$${Number(x.price).toLocaleString()}`)
      .join(" · ");
    levelsEl.textContent =
      `BTC $${Number(lv.spot).toLocaleString()} · 90d high $${Number(lv.high_90d).toLocaleString()} ` +
      `(${lv.drawdown_90d_pct}%) · 45d low $${Number(lv.low_45d).toLocaleString()} · limits: ${buys}`;
  } else {
    levelsEl.textContent = "";
  }
  note.textContent = [cycle.macro_context, cycle.note].filter(Boolean).join(" ");
}

function renderActionPlan(plan) {
  window.__lastActionPlan = plan || {};
  const card = document.getElementById("action-plan-card");
  const badge = document.getElementById("action-mode-badge");
  const headline = document.getElementById("action-headline");
  const checklist = document.getElementById("action-checklist");
  const sellsBody = document.getElementById("action-sells-body");
  const sellsWrap = document.getElementById("action-sells-wrap");
  const note = document.getElementById("action-note");
  const rules = document.getElementById("action-rules");
  if (!card || !plan) return;

  const mode = plan.mode || "hold";
  card.dataset.mode = mode;
  badge.textContent = mode;
  badge.className = `badge mode-${mode}`;
  headline.textContent = plan.headline || "—";

  const items = plan.checklist || [];
  checklist.innerHTML = items.length
    ? items.map((t) => `<li>${t}</li>`).join("")
    : "<li>No checklist</li>";

  const actions = plan.actions || [];
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
        <td class="neg">−${usd(a.sell_usdt)}</td>
        <td>${a.pct_of_bag}%</td>
        <td>${a.reason || "—"}</td>
      </tr>`
      )
      .join("");
  }

  note.textContent = plan.note || "";
  if (rules && plan.rules) {
    const r = plan.rules;
    rules.textContent = [r.profit_lock, r.example, r.defense, r.min_impact]
      .filter(Boolean)
      .join(" · ");
  }
  const lockStatus = document.getElementById("lock-status");
  const already = plan.already_locked_usdt || 0;
  const remain = plan.lock_remaining_usdt;
  const target = plan.lock_target_usdt;
  if (lockStatus && !window.__lockFlash) {
    lockStatus.className = "status";
    lockStatus.textContent =
      target > 0
        ? `Locked today: $${Number(already).toFixed(2)} / target $${Number(target).toFixed(2)}` +
          (remain > 0 && plan.mode === "profit_lock" ? ` · still $${Number(remain).toFixed(2)}` : " · done")
        : `Locked today: $${Number(already).toFixed(2)}`;
  }
}

document.getElementById("lock-detect-btn")?.addEventListener("click", async () => {
  const status = document.getElementById("lock-status");
  const btn = document.getElementById("lock-detect-btn");
  if (!status) {
    alert("lock-status missing — hard-refresh the page (Ctrl+Shift+R)");
    return;
  }
  if (btn) btn.disabled = true;
  status.className = "status";
  status.textContent = "Reading Binance sells (today + ~90d)… may take ~30–60s";
  window.__lockFlash = status.textContent;
  try {
    const res = await fetchJson("/api/profit-lock/detect", { method: "POST" });
    const total = (res.detected && res.detected.total_usdt) || 0;
    const rangeTotal = (res.detected && res.detected.range_total_usdt) || 0;
    const by = (res.detected && res.detected.by_symbol) || {};
    const errs = (res.detected && res.detected.errors) || [];
    const detail = Object.entries(by)
      .map(([s, v]) => `${s} $${v}`)
      .join(", ");
    let msg = total
      ? `TP sells today: $${total}${detail ? ` (${detail})` : ""}`
      : (res.detected && res.detected.message) || "No sells detected today";
    const filt = res.take_profit_filter || {};
    const kept = filt.kept_days || [];
    const skipped = filt.skipped || [];
    if (kept.length) msg += ` · TP days: ${kept.join(", ")}`;
    if (skipped.length) msg += ` · skipped ${skipped.length} non-TP day(s)`;
    const periods = (res.ledger && res.ledger.periods) || {};
    const q = periods.quarter && periods.quarter.locked_usdt;
    if (q != null) msg += ` · 3mo TP $${q}`;
    window.__lockFlash = msg;
    status.textContent = msg;
    status.className = (total || kept.length) ? "status" : "status error";
    await refresh();
    if (window.__lockFlash) {
      const el = document.getElementById("lock-status");
      el.textContent = window.__lockFlash;
      el.className = (total || kept.length) ? "status" : "status error";
      setTimeout(() => { window.__lockFlash = null; }, 10000);
    }
  } catch (err) {
    const msg = `Detect failed: ${err.message}`;
    window.__lockFlash = msg;
    status.className = "status error";
    status.textContent = msg;
    if (String(err.message).includes("Not Found") || String(err.message).includes("404")) {
      status.textContent =
        "Detect API 404 — server is running old code. Restart: python -m src.web";
    }
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("lock-reset-btn")?.addEventListener("click", async () => {
  if (!confirm("Reset today's locked amount?")) return;
  window.__lockFlash = null;
  await fetchJson("/api/profit-lock/reset", { method: "POST" });
  await refresh();
});

function renderRebalance(rebalance) {
  const policy = document.getElementById("rebalance-policy");
  const body = document.getElementById("rebalance-body");
  if (policy && rebalance.policy) policy.textContent = rebalance.policy;

  const rows = [...(rebalance.actionable || []), ...(rebalance.minor || [])];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7" style="color:var(--muted)">All within thresholds — no rebalance needed (save fees).</td></tr>`;
    return;
  }

  body.innerHTML = rows
    .map(
      (r) => `
    <tr>
      <td><strong>${r.asset}</strong></td>
      <td><span class="badge ${r.action}">${r.action}</span></td>
      <td>${r.current_pct}%</td>
      <td>${r.target_pct}%</td>
      <td class="${r.deviation_pct >= 0 ? "pos" : "neg"}">${r.deviation_pct > 0 ? "+" : ""}${r.deviation_pct}%</td>
      <td>${r.amount_usdt > 0 ? "+" : ""}${usd(r.amount_usdt)}</td>
      <td>${r.note || "—"}</td>
    </tr>`
    )
    .join("");
}

function renderAllocation(rebalance) {
  const body = document.getElementById("allocation-body");
  const rows = rebalance.allocation || [];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5" style="color:var(--muted)">No allocation data</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((r) => {
      const gapCls = Math.abs(r.gap_pct) < 1 ? "" : r.gap_pct > 0 ? "pos" : "neg";
      return `
      <tr>
        <td><strong>${r.asset}</strong></td>
        <td>${r.current_pct}%</td>
        <td>${r.target_pct}%</td>
        <td class="${gapCls}">${r.gap_pct > 0 ? "+" : ""}${r.gap_pct}%</td>
        <td>${usd(r.value_usdt)}</td>
      </tr>`;
    })
    .join("");
}

function renderHoldings(portfolio, rebalance) {
  const body = document.getElementById("portfolio-body");
  if (!portfolio || !portfolio.available) {
    body.innerHTML = `<tr><td colspan="7" style="color:var(--muted)">Set EXCHANGE_API_KEY in .env</td></tr>`;
    return;
  }

  const targets = (rebalance && rebalance.targets) || {};
  const holdings = holdingsFromPortfolio(portfolio);
  body.innerHTML =
    holdings
      .map((h) => {
        const target = targets[h.symbol];
        const gap = target == null ? null : Number(h.pct) - Number(target);
        return `
    <tr>
      <td><strong>${h.symbol}</strong> <span class="badge">${h.asset_class || "crypto"}</span></td>
      <td>${qtyFmt(h.quantity)}</td>
      <td>${h.price_usdt == null ? "—" : usd(h.price_usdt)}</td>
      <td>${usd(h.value_usdt)}</td>
      <td>${h.pct}%</td>
      <td>${target == null ? "—" : `${target}%`}</td>
      <td class="${gap == null ? "" : gap >= 0 ? "pos" : "neg"}">${
        gap == null ? "—" : `${gap > 0 ? "+" : ""}${gap.toFixed(2)}%`
      }</td>
    </tr>`;
      })
      .join("") || `<tr><td colspan="7" style="color:var(--muted)">No assets</td></tr>`;
}

async function refresh() {
  const status = document.getElementById("last-run");
  try {
    const [state, signals, portfolio, overview, accounts, cfg, paper] = await Promise.all([
      fetchJson("/api/state"),
      fetchJson("/api/signals?limit=80"),
      fetchJson("/api/portfolio"),
      fetchJson("/api/overview"),
      fetchJson("/api/accounts"),
      fetchJson("/api/config"),
      fetchJson("/api/paper"),
    ]);

    status.className = "status";
    status.textContent = overview.last_synced_at
      ? `Last sync: ${overview.last_synced_at.replace("T", " ").slice(0, 19)}`
      : state.last_run
        ? `Last run: ${state.last_run.replace("T", " ")}`
        : "Last sync: —";
    if (state.error) {
      status.className = "status error";
      status.textContent += ` · ${state.error}`;
    }
    if (portfolio && portfolio.available === false && portfolio.message) {
      status.className = "status error";
      status.textContent = portfolio.message;
    }

    renderConfig(cfg || portfolio.config);
    setModeButtons((cfg && cfg.strategy_mode) || state.strategy_mode || "both");
    renderAccounts(accounts);
    renderMarkets(state.markets || {});
    renderAlerts(signals.signals || state.alerts || []);
    renderSignals(signals.signals || []);
    renderNews(state.news || []);
    renderOverview(overview, portfolio);
    renderPaper(paper || state.paper);
  } catch (err) {
    status.className = "status error";
    status.textContent = `Refresh failed: ${err.message}`;
  }
}

document.getElementById("sync-btn").addEventListener("click", async () => {
  const btn = document.getElementById("sync-btn");
  const status = document.getElementById("last-run");
  btn.disabled = true;
  btn.textContent = "Syncing…";
  try {
    const results = await fetchJson("/api/sync", { method: "POST" });
    const bad = (results || []).filter((r) => r.status === "error");
    if (bad.length) {
      status.className = "status error";
      status.textContent = bad.map((r) => `${r.source}: ${r.message}`).join(" · ");
    }
    await refresh();
  } catch (err) {
    status.className = "status error";
    status.textContent = `Sync failed: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Sync portfolio";
  }
});

document.getElementById("reload-btn").addEventListener("click", () => refresh());

document.getElementById("reset-paper-btn").addEventListener("click", async () => {
  if (!confirm("Reset local demo paper account? Open/closed virtual trades will be wiped.")) return;
  const status = document.getElementById("last-run");
  try {
    const res = await fetchJson("/api/paper/reset", { method: "POST" });
    status.className = "status";
    status.textContent = res.message || "Paper reset";
    await refresh();
  } catch (err) {
    status.className = "status error";
    status.textContent = `Reset failed: ${err.message}`;
  }
});

document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const mode = btn.dataset.mode;
    try {
      await fetchJson("/api/strategy-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      setModeButtons(mode);
      await fetchJson("/api/sync", { method: "POST" });
      await refresh();
    } catch (err) {
      document.getElementById("last-run").className = "status error";
      document.getElementById("last-run").textContent = `Mode switch failed: ${err.message}`;
    }
  });
});

refresh();
setInterval(refresh, 30000);
