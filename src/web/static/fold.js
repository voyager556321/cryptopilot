/** Collapsible sections (editor-like code folding). */
(function () {
  const STORAGE_KEY = "trading-ui-folds:" + (location.pathname || "/");

  function loadState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
    } catch (_) {
      return {};
    }
  }

  function saveState(state) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (_) {}
  }

  function sectionId(section, index) {
    if (section.dataset.foldId) return section.dataset.foldId;
    const h2 = section.querySelector(":scope > h2, :scope > .section-head h2");
    const raw = (h2 && h2.textContent) || `section-${index}`;
    return raw.trim().toLowerCase().replace(/\s+/g, "-").slice(0, 48);
  }

  function defaultCollapsed(section) {
    const raw = (section.dataset.foldDefault || "").toLowerCase();
    return raw === "collapsed" || raw === "1" || raw === "true";
  }

  function wrapBody(section, headEl) {
    if (section.querySelector(":scope > .section-body")) return section.querySelector(":scope > .section-body");
    const body = document.createElement("div");
    body.className = "section-body";
    const move = [];
    let node = headEl.nextSibling;
    while (node) {
      const next = node.nextSibling;
      move.push(node);
      node = next;
    }
    move.forEach((n) => body.appendChild(n));
    section.appendChild(body);
    return body;
  }

  function applyFold(section, collapsed) {
    section.classList.toggle("is-collapsed", collapsed);
    const btn = section.querySelector(":scope > .section-head");
    if (btn) btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }

  function initSectionFolding() {
    const state = loadState();
    document.querySelectorAll(".section").forEach((section, index) => {
      if (section.dataset.foldReady) return;
      const h2 = section.querySelector(":scope > h2");
      if (!h2) return;

      const id = sectionId(section, index);
      section.dataset.foldId = id;
      section.dataset.foldReady = "1";

      const head = document.createElement("button");
      head.type = "button";
      head.className = "section-head";
      head.setAttribute("aria-expanded", "true");

      const chevron = document.createElement("span");
      chevron.className = "fold-chevron";
      chevron.setAttribute("aria-hidden", "true");
      chevron.textContent = "▾";

      h2.replaceWith(head);
      head.appendChild(chevron);
      head.appendChild(h2);

      wrapBody(section, head);

      // localStorage wins if user toggled; else honor data-fold-default
      const collapsed = Object.prototype.hasOwnProperty.call(state, id)
        ? Boolean(state[id])
        : defaultCollapsed(section);
      applyFold(section, collapsed);

      head.addEventListener("click", () => {
        const next = !section.classList.contains("is-collapsed");
        applyFold(section, next);
        const s = loadState();
        s[id] = next; // true = collapsed, false = expanded (remember user choice)
        saveState(s);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSectionFolding);
  } else {
    initSectionFolding();
  }

  window.initSectionFolding = initSectionFolding;
})();
