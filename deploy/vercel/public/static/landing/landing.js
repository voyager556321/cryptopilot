/** CryptoPilot marketing landing — isolated from dashboard JS */

(function () {
  const toggle = document.getElementById("nav-toggle");
  const mobile = document.getElementById("mobile-nav");
  if (toggle && mobile) {
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", open ? "false" : "true");
      mobile.hidden = open;
    });
    mobile.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => {
        toggle.setAttribute("aria-expanded", "false");
        mobile.hidden = true;
      });
    });
  }

  const form = document.getElementById("waitlist-form");
  const status = document.getElementById("waitlist-status");
  const emailInput = document.getElementById("waitlist-email");

  function setStatus(msg, kind) {
    if (!status) return;
    status.textContent = msg;
    status.className = "lp-form-status" + (kind ? ` is-${kind}` : "");
  }

  if (form && emailInput) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = String(emailInput.value || "").trim();
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        setStatus("Enter a valid email address.", "err");
        emailInput.focus();
        return;
      }
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      setStatus("Joining…", "");
      try {
        const res = await fetch("/api/waitlist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, source: "landing" }),
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(body.error || body.message || res.statusText);
        }
        setStatus(body.message || "You're on the list. We'll be in touch.", "ok");
        form.reset();
        if (typeof window.va === "function") {
          window.va("event", { name: "WaitlistSignup" });
        }
      } catch (err) {
        setStatus(err.message || "Something went wrong. Try again.", "err");
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  }
})();
