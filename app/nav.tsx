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
          <a href="#before-after">Before / After</a>
          <a href="#how">How it works</a>
          <a href="#proof">Proof</a>
          <a href="#waitlist">Waitlist</a>
        </nav>
        <a className="lp-btn lp-btn-sm" href="#waitlist">
          Join Waitlist
        </a>
        <button
          type="button"
          className="lp-nav-toggle"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label="Open menu"
          onClick={() => setOpen((v) => !v)}
        >
          <span></span>
          <span></span>
        </button>
      </div>
      <nav className="lp-mobile-nav" id="mobile-nav" hidden={!open}>
        <a href="#before-after" onClick={() => setOpen(false)}>
          Before / After
        </a>
        <a href="#how" onClick={() => setOpen(false)}>
          How it works
        </a>
        <a href="#outcomes" onClick={() => setOpen(false)}>
          Outcomes
        </a>
        <a href="#proof" onClick={() => setOpen(false)}>
          Proof
        </a>
        <a href="#story" onClick={() => setOpen(false)}>
          Story
        </a>
        <a href="#waitlist" onClick={() => setOpen(false)}>
          Waitlist
        </a>
        <a href="mailto:hello@cryptopilot.app">Contact</a>
      </nav>
    </header>
  );
}
