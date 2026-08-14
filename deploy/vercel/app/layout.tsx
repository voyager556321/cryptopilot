import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./landing.css";

export const metadata: Metadata = {
  title: "CryptoPilot — Know what to do with your crypto portfolio today",
  description:
    "Open the app. Know what to do today. Daily hold, profit-lock, defense, and rebalance guidance for your crypto portfolio — advice only, no auto-orders.",
  openGraph: {
    title: "CryptoPilot — Know what to do with your crypto portfolio today",
    description:
      "Open the app. Know what to do today. One daily decision for your portfolio — hold, lock profit, defend, or rebalance.",
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
