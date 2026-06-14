import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentRanker — Trust Layer for the AI Agent Economy",
  description:
    "On-chain reputation scoring, sybil-resistant rankings, and trust-gated payments for AI agents. Built on Hedera + ERC-8004.",
  keywords: ["AI agents", "trust layer", "Hedera", "ERC-8004", "reputation", "blockchain"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="antialiased" style={{ background: "#050510" }}>
        {children}
      </body>
    </html>
  );
}
