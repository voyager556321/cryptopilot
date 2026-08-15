import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./landing.css";

export const metadata: Metadata = {
  title: "CryptoPilot — Portfolio discipline engine (not a trading bot)",
  description:
    "Know what to do with your crypto portfolio today. A discipline engine for hold, profit-lock, defense, and rebalance — advice only, no auto-orders. Not AI signals.",
  openGraph: {
    title: "CryptoPilot — Portfolio discipline engine",
    description:
      "Help yourself follow your own rules when emotion would otherwise decide. Advice only — no auto-orders.",
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
