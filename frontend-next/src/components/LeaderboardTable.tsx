"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { Agent } from "@/lib/api";

interface LeaderboardTableProps {
  agents: Agent[];
  isLoading: boolean;
}

function HexRank({ rank }: { rank: number }) {
  return (
    <div className="relative flex items-center justify-center w-8 h-8 flex-shrink-0">
      <svg viewBox="0 0 32 32" className="absolute inset-0 w-full h-full">
        <polygon
          points="16,2 29,8.5 29,23.5 16,30 3,23.5 3,8.5"
          fill="rgba(108,99,255,0.15)"
          stroke="#6c63ff"
          strokeWidth="1.5"
        />
      </svg>
      <span
        className="relative z-10 text-xs font-bold"
        style={{ color: rank <= 3 ? "#6c63ff" : "#94a3b8" }}
      >
        {rank}
      </span>
    </div>
  );
}

function TrustBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8 ? "#4ade80" : score >= 0.6 ? "#6c63ff" : score >= 0.4 ? "#f59e0b" : "#f87171";

  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-24 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: `linear-gradient(90deg, ${color}, ${color}99)` }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span
        className="text-xs font-bold font-mono"
        style={{ color, fontFamily: "JetBrains Mono, monospace" }}
      >
        {score.toFixed(3)}
      </span>
    </div>
  );
}

function Badge({ label, color, bg }: { label: string; color: string; bg: string }) {
  return (
    <span
      className="inline-block px-1.5 py-0.5 rounded text-xs font-semibold"
      style={{ background: bg, color, border: `1px solid ${color}30` }}
    >
      {label}
    </span>
  );
}

function ShieldIcon({ protected: isProtected }: { protected: boolean }) {
  return (
    <div
      className="flex items-center gap-1 text-xs"
      title={isProtected ? "Sybil-resistant validated" : "Not sybil-validated"}
    >
      <svg width="14" height="16" viewBox="0 0 14 16" fill="none">
        <path
          d="M7 1L13 3.5V8C13 11.5 10.5 14.5 7 15.5C3.5 14.5 1 11.5 1 8V3.5L7 1Z"
          fill={isProtected ? "rgba(74,222,128,0.15)" : "rgba(255,255,255,0.04)"}
          stroke={isProtected ? "#4ade80" : "#475569"}
          strokeWidth="1.2"
        />
        {isProtected && (
          <path
            d="M4.5 8L6.5 10L9.5 6.5"
            stroke="#4ade80"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
      </svg>
      <span style={{ color: isProtected ? "#4ade80" : "#475569" }}>
        {isProtected ? "Protected" : "Unvalidated"}
      </span>
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div
            className="h-4 rounded animate-pulse"
            style={{ background: "rgba(255,255,255,0.05)", width: `${60 + Math.random() * 40}%` }}
          />
        </td>
      ))}
    </tr>
  );
}

export default function LeaderboardTable({ agents, isLoading }: LeaderboardTableProps) {
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      {/* Header */}
      <div className="px-6 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <h3 className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
          Agent Leaderboard
        </h3>
        <p className="text-xs mt-0.5" style={{ color: "#64748b" }}>
          Ranked by combined ERC-8004 reputation + RAGAS evaluation scores
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
              {["Rank", "Agent", "Trust Score", "Capability", "Badges", "Trust Shield", "Topic ID"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider"
                  style={{ color: "#64748b" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
            ) : agents.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center" style={{ color: "#64748b" }}>
                  No agents found. Make sure the backend is running on port 8000.
                </td>
              </tr>
            ) : (
              agents.map((agent, idx) => {
                const isHovered = hoveredRow === agent.agent_id;
                const isTop3 = idx < 3;

                return (
                  <motion.tr
                    key={agent.agent_id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: idx * 0.04 }}
                    onMouseEnter={() => setHoveredRow(agent.agent_id)}
                    onMouseLeave={() => setHoveredRow(null)}
                    style={{
                      borderBottom: "1px solid rgba(255,255,255,0.04)",
                      background: isHovered
                        ? "rgba(108,99,255,0.06)"
                        : isTop3
                        ? "rgba(108,99,255,0.02)"
                        : "transparent",
                      transition: "background 0.2s",
                    }}
                  >
                    {/* Rank */}
                    <td className="px-4 py-3">
                      <HexRank rank={idx + 1} />
                    </td>

                    {/* Agent name + description */}
                    <td className="px-4 py-3">
                      <div>
                        <div
                          className="text-sm font-semibold"
                          style={{ color: isTop3 ? "#e2e8f0" : "#cbd5e1" }}
                        >
                          {agent.name}
                        </div>
                        <div
                          className="text-xs mt-0.5 max-w-xs truncate"
                          style={{ color: "#64748b" }}
                          title={agent.description}
                        >
                          {agent.description}
                        </div>
                        {agent.erc8004_address && (
                          <div
                            className="text-xs mt-0.5 font-mono truncate max-w-[180px]"
                            style={{ color: "#475569", fontFamily: "JetBrains Mono, monospace" }}
                            title={agent.erc8004_address}
                          >
                            {agent.erc8004_address.slice(0, 6)}...{agent.erc8004_address.slice(-4)}
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Trust score bar */}
                    <td className="px-4 py-3">
                      <TrustBar score={agent.trust_score} />
                      {agent.erc8004_reputation !== null && (
                        <div className="text-xs mt-0.5" style={{ color: "#64748b" }}>
                          ERC-8004: {agent.erc8004_reputation}/100
                        </div>
                      )}
                    </td>

                    {/* Capability */}
                    <td className="px-4 py-3">
                      <span
                        className="text-xs px-2 py-1 rounded-full"
                        style={{
                          background: "rgba(62,207,207,0.08)",
                          color: "#3ecfcf",
                          border: "1px solid rgba(62,207,207,0.2)",
                        }}
                      >
                        {agent.capability}
                      </span>
                    </td>

                    {/* Badges */}
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {agent.supports_x402 && (
                          <Badge label="x402" color="#3ecfcf" bg="rgba(62,207,207,0.1)" />
                        )}
                        {agent.is_serviceable && (
                          <Badge label="Live" color="#4ade80" bg="rgba(74,222,128,0.1)" />
                        )}
                        {agent.domain && (
                          <Badge label={agent.domain} color="#a5b4fc" bg="rgba(108,99,255,0.1)" />
                        )}
                      </div>
                    </td>

                    {/* Trust shield */}
                    <td className="px-4 py-3">
                      <ShieldIcon protected={agent.trust_score >= 0.6} />
                    </td>

                    {/* Hedera topic */}
                    <td className="px-4 py-3">
                      {agent.hedera_topic_id ? (
                        <span
                          className="text-xs font-mono"
                          style={{ color: "#6c63ff", fontFamily: "JetBrains Mono, monospace" }}
                        >
                          {agent.hedera_topic_id}
                        </span>
                      ) : (
                        <span className="text-xs" style={{ color: "#374151" }}>
                          —
                        </span>
                      )}
                    </td>
                  </motion.tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {!isLoading && agents.length > 0 && (
        <div
          className="px-6 py-3 text-xs"
          style={{ borderTop: "1px solid rgba(255,255,255,0.05)", color: "#64748b" }}
        >
          Showing {agents.length} agents · Live data from BigQuery + RAGAS
        </div>
      )}
    </div>
  );
}
