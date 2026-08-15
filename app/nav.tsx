"use client";

import { useState } from "react";

export default function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="lp-nav" id="top">
      <div className="lp-nav-inner">
        <a className="lp-logo" href="/">
          CryptoPilot
        </a>
        <nav className="lp-nav-links" aria-label="Primary">
          <a href="#demo">Demo</a>
          <a href="#trust">Why trust</a>
          <a href="#story">Story</a>
          <a href="#waitlist">Early Access</a>
        </nav>
        <a className="lp-btn lp-btn-sm" href="#demo">
          Try Demo
        </a>
        <button
          type="button"
          className="lp-nav-toggle"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          <span></span>
          <span></span>
        </button>
      </div>
      <nav
        className={"lp-mobile-nav" + (open ? " is-open" : "")}
        id="mobile-nav"
      >
        <a href="#demo" onClick={() => setOpen(false)}>
          Demo
        </a>
        <a href="#trust" onClick={() => setOpen(false)}>
          Why trust
        </a>
        <a href="#story" onClick={() => setOpen(false)}>
          Story
        </a>
        <a href="#waitlist" onClick={() => setOpen(false)}>
          Early Access
        </a>
        <a href="mailto:hello@cryptopilot.app">Contact</a>
      </nav>
    </header>
  );
}
