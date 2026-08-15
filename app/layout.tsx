import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./landing.css";

export const metadata: Metadata = {
  title: "CryptoPilot — Daily portfolio decisions (not a trading bot)",
  description:
    "Know what to do with your crypto portfolio today. Hold, profit-lock, defense, rebalance — advice only, no auto-orders. Not an AI trading bot or signal channel.",
  openGraph: {
    title: "CryptoPilot — Daily portfolio decisions (not a trading bot)",
    description:
      "One daily decision with reasons. Advice only — no auto-orders. Built as a personal exit process, not a signals product.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0f1117",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="lp">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
