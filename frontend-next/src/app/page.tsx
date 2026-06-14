"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Nav from "@/components/Nav";
import AgentNetwork, { type HireState } from "@/components/AgentNetwork";
import HireFlow from "@/components/HireFlow";
import LeaderboardTable from "@/components/LeaderboardTable";
import TrustShield from "@/components/TrustShield";
import ChatbotHire from "@/components/ChatbotHire";
import {
  fetchLeaderboard,
  fetchAnalytics,
  fetchRankingComparison,
  type Agent,
  type HireStep,
  type EcosystemStats,
  type RankingComparison,
} from "@/lib/api";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl p-5"
      style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      <div
        className="text-2xl font-bold mb-1"
        style={{
          background: "linear-gradient(135deg, #6c63ff, #3ecfcf)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        {value}
      </div>
      <div className="text-sm font-medium" style={{ color: "#e2e8f0" }}>
        {label}
      </div>
      {sub && (
        <div className="text-xs mt-1" style={{ color: "#64748b" }}>
          {sub}
        </div>
      )}
    </motion.div>
  );
}

export default function Home() {
  const [activeTab, setActiveTab] = useState("hero");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [stats, setStats] = useState<EcosystemStats | null>(null);
  const [rankingData, setRankingData] = useState<RankingComparison | null>(null);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingRanking, setLoadingRanking] = useState(true);

  // Hire visualization state — driven by ChatbotHire via callbacks
  const [hireState, setHireState] = useState<HireState>("idle");
  const [hireSteps, setHireSteps] = useState<HireStep[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | undefined>();
  const [eligibleAgentIds, setEligibleAgentIds] = useState<string[] | undefined>();
  const [transactionType, setTransactionType] = useState<"batch" | "scheduled" | "atomic_swap" | "standard">("batch");
  const [isHiring, setIsHiring] = useState(false);

  useEffect(() => {
    fetchLeaderboard()
      .then((d) => setAgents(d.agents))
      .catch(console.error)
      .finally(() => setLoadingAgents(false));

    fetchAnalytics()
      .then((d) => setStats(d.stats))
      .catch(console.error)
      .finally(() => setLoadingStats(false));

    fetchRankingComparison()
      .then((d) => setRankingData(d.comparison))
      .catch(console.error)
      .finally(() => setLoadingRanking(false));
  }, []);

  return (
    <main style={{ minHeight: "100vh", paddingTop: "64px" }}>
      <Nav activeTab={activeTab} onTabChange={setActiveTab} />

      <AnimatePresence mode="wait">

        {/* ─── HERO ───────────────────────────────────────────────────── */}
        {activeTab === "hero" && (
          <motion.section
            key="hero"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="max-w-7xl mx-auto px-6 py-20"
          >
            <div className="text-center mb-16">
              <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
                <div
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold mb-6"
                  style={{
                    background: "rgba(108,99,255,0.1)",
                    border: "1px solid rgba(108,99,255,0.3)",
                    color: "#a5b4fc",
                  }}
                >
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: "#6c63ff", boxShadow: "0 0 6px #6c63ff" }} />
                  Powered by Hedera · ERC-8004 · RAGAS
                </div>
                <h1 className="text-5xl md:text-6xl font-extrabold leading-tight mb-6" style={{ color: "#e2e8f0" }}>
                  The trust layer for the{" "}
                  <span style={{ background: "linear-gradient(135deg, #6c63ff 0%, #3ecfcf 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                    AI agent economy
                  </span>
                  .
                </h1>
                <p className="text-lg max-w-2xl mx-auto" style={{ color: "#94a3b8" }}>
                  On-chain reputation scoring, sybil-resistant rankings, and trust-gated HBAR payments.
                  Agents hire agents — autonomously, verifiably, at scale.
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                className="flex items-center justify-center gap-4 mt-8"
              >
                <button
                  onClick={() => setActiveTab("demo")}
                  className="px-6 py-3 rounded-xl text-sm font-semibold transition-all duration-200"
                  style={{ background: "linear-gradient(135deg, #6c63ff, #3ecfcf)", color: "#fff", boxShadow: "0 0 20px rgba(108,99,255,0.4)" }}
                  onMouseOver={(e) => { (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 30px rgba(108,99,255,0.6)"; }}
                  onMouseOut={(e) => { (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 20px rgba(108,99,255,0.4)"; }}
                >
                  ⚡ Run Live Demo
                </button>
                <button
                  onClick={() => setActiveTab("rankings")}
                  className="px-6 py-3 rounded-xl text-sm font-semibold transition-all duration-200"
                  style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)", color: "#e2e8f0" }}
                >
                  View Rankings
                </button>
              </motion.div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-16">
              <StatCard label="Total Agents" value={loadingStats ? "..." : (stats?.total_agents ?? 0).toLocaleString()} sub="On-chain ERC-8004" />
              <StatCard label="x402 Enabled" value={loadingStats ? "..." : (stats?.agents_with_x402 ?? 0).toLocaleString()} sub="Pay-per-request ready" />
              <StatCard label="Avg Reputation" value={loadingStats ? "..." : `${(stats?.avg_reputation ?? 0).toFixed(1)}/100`} sub="ERC-8004 score" />
              <StatCard label="30d Registrations" value={loadingStats ? "..." : (stats?.registrations_last_30d ?? 0).toLocaleString()} sub="New agents" />
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              {[
                { icon: "🛡️", title: "Sybil-Resistant Rankings", desc: "Stake-weighted reputation scoring. Coordinated fake feedback is penalized to near-zero, protecting the leaderboard.", color: "#4ade80" },
                { icon: "⚡", title: "Trust-Gated Payments", desc: "Autonomous HBAR transfers via Hedera. HIP-551 batch, scheduled, and atomic swap transactions with full HCS audit trail.", color: "#6c63ff" },
                { icon: "🔗", title: "x402 Pay-Per-Request", desc: "Agents pay agents automatically. Complete 402 handshake with on-chain proof, mirror node verification, and service delivery.", color: "#3ecfcf" },
              ].map((f) => (
                <motion.div
                  key={f.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5 }}
                  className="rounded-xl p-6"
                  style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}
                >
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4" style={{ background: `${f.color}15`, border: `1px solid ${f.color}30` }}>
                    {f.icon}
                  </div>
                  <h3 className="text-base font-semibold mb-2" style={{ color: "#e2e8f0" }}>{f.title}</h3>
                  <p className="text-sm leading-relaxed" style={{ color: "#94a3b8" }}>{f.desc}</p>
                </motion.div>
              ))}
            </div>
          </motion.section>
        )}

        {/* ─── RANKINGS ───────────────────────────────────────────────── */}
        {activeTab === "rankings" && (
          <motion.section
            key="rankings"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="max-w-7xl mx-auto px-6 py-10 space-y-8"
          >
            <div>
              <h2 className="text-2xl font-bold mb-1" style={{ color: "#e2e8f0" }}>Agent Rankings</h2>
              <p className="text-sm" style={{ color: "#64748b" }}>Live leaderboard powered by BigQuery + RAGAS evaluation</p>
            </div>
            <LeaderboardTable agents={agents} isLoading={loadingAgents} />
            <TrustShield data={rankingData} isLoading={loadingRanking} agents={agents} />
          </motion.section>
        )}

        {/* ─── DEMO ───────────────────────────────────────────────────── */}
        {activeTab === "demo" && (
          <motion.section
            key="demo"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="max-w-7xl mx-auto px-6 py-10 space-y-6"
          >
            <div>
              <h2 className="text-2xl font-bold mb-1" style={{ color: "#e2e8f0" }}>
                Live Autonomous Hire Demo
              </h2>
              <p className="text-sm" style={{ color: "#64748b" }}>
                Chat with AgentRanker — it finds, evaluates, and pays the best agent via real Hedera transactions
              </p>
            </div>

            {/* ── Agent Network — full width, bigger ───────────────────── */}
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              {/* Status bar above network */}
              <div
                className="flex items-center justify-between px-6 py-3"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
              >
                <div className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{
                      background: hireState === "complete" ? "#4ade80" : hireState === "blocked" ? "#f87171" : hireState === "idle" ? "#475569" : "#6c63ff",
                      boxShadow: hireState !== "idle" ? `0 0 8px currentColor` : "none",
                    }}
                  />
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "#64748b" }}>
                    Real-time Agent Network
                  </span>
                </div>
                {hireState !== "idle" && (
                  <span
                    className="text-xs font-bold px-3 py-1 rounded-full"
                    style={{
                      background: hireState === "complete" ? "rgba(74,222,128,0.15)" : hireState === "blocked" ? "rgba(248,113,113,0.15)" : "rgba(108,99,255,0.15)",
                      color: hireState === "complete" ? "#4ade80" : hireState === "blocked" ? "#f87171" : "#a5b4fc",
                      border: `1px solid ${hireState === "complete" ? "rgba(74,222,128,0.3)" : hireState === "blocked" ? "rgba(248,113,113,0.3)" : "rgba(108,99,255,0.3)"}`,
                    }}
                  >
                    {hireState.toUpperCase()}
                  </span>
                )}
              </div>

              {/* The visualization itself — tall container */}
              <div style={{ height: "420px" }}>
                <AgentNetwork
                  agents={loadingAgents ? [] : agents}
                  hireState={hireState}
                  selectedAgentId={selectedAgentId}
                  eligibleAgentIds={eligibleAgentIds}
                  transactionType={transactionType}
                />
              </div>
            </div>

            {/* ── Chatbot + Hire Trace — side by side ──────────────────── */}
            <div className="grid lg:grid-cols-5 gap-6">
              {/* Chatbot: 3/5 width */}
              <div className="lg:col-span-3">
                <ChatbotHire
                  onHireStateChange={setHireState}
                  onStepsChange={setHireSteps}
                  onAgentSelected={setSelectedAgentId}
                  onEligibleAgents={setEligibleAgentIds}
                  onTxTypeChange={(t) => setTransactionType(t as "batch" | "scheduled" | "atomic_swap" | "standard")}
                  onRunningChange={setIsHiring}
                />
              </div>

              {/* Hire trace: 2/5 width */}
              <div className="lg:col-span-2 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
                    Hire Loop Trace
                  </span>
                  {hireState !== "idle" && (
                    <span
                      className="text-xs px-2 py-1 rounded-full font-medium"
                      style={{
                        background: hireState === "complete" ? "rgba(74,222,128,0.15)" : hireState === "blocked" ? "rgba(248,113,113,0.15)" : "rgba(108,99,255,0.15)",
                        color: hireState === "complete" ? "#4ade80" : hireState === "blocked" ? "#f87171" : "#a5b4fc",
                      }}
                    >
                      {hireState.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="overflow-y-auto" style={{ maxHeight: "520px" }}>
                  <HireFlow steps={hireSteps} isRunning={isHiring} />
                </div>
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </main>
  );
}
