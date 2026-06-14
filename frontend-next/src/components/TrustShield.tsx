"use client";

import { motion } from "framer-motion";
import type { RankingComparison, Agent } from "@/lib/api";

interface TrustShieldProps {
  data: RankingComparison | null;
  isLoading: boolean;
  agents?: Agent[];
}

function RankDelta({ delta }: { delta: number }) {
  if (delta === 0) {
    return (
      <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.05)", color: "#64748b" }}>
        ─ same
      </span>
    );
  }
  const improved = delta > 0;
  return (
    <span
      className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded font-semibold"
      style={{
        background: improved ? "rgba(74,222,128,0.1)" : "rgba(248,113,113,0.1)",
        color: improved ? "#4ade80" : "#f87171",
      }}
    >
      {improved ? "↑" : "↓"} {Math.abs(delta)}
    </span>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded animate-pulse flex-1"
          style={{ background: "rgba(255,255,255,0.05)" }}
        />
      ))}
    </div>
  );
}

function shortId(agent_id: string): string {
  // Full 64-char hex like 0x000...3841 → "Agent 0x…3841"
  if (/^0x[0-9a-f]{10,}$/i.test(agent_id)) {
    return `Agent 0x…${agent_id.slice(-4)}`;
  }
  return agent_id
    .replace(/^agent-/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function TrustShield({ data, isLoading, agents = [] }: TrustShieldProps) {
  const getName = (agent_id: string) => {
    const found = agents.find((a) => a.agent_id === agent_id);
    return found?.name ?? shortId(agent_id);
  };
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      {/* Header */}
      <div className="px-6 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: "rgba(74,222,128,0.1)", border: "1px solid rgba(74,222,128,0.3)" }}
          >
            <svg width="20" height="22" viewBox="0 0 20 22" fill="none">
              <path
                d="M10 1L19 5V11C19 16 15 20.5 10 21.5C5 20.5 1 16 1 11V5L10 1Z"
                fill="rgba(74,222,128,0.15)"
                stroke="#4ade80"
                strokeWidth="1.5"
              />
              <path
                d="M6.5 11L9 13.5L13.5 8"
                stroke="#4ade80"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
              Sybil-Resistant Trust Shield
            </h3>
            <p className="text-xs" style={{ color: "#64748b" }}>
              Naive vs. weighted ranking comparison
            </p>
          </div>
          {data && (
            <div className="ml-auto">
              <span
                className="text-xs font-bold px-3 py-1 rounded-full"
                style={{
                  background: "rgba(248,113,113,0.1)",
                  color: "#f87171",
                  border: "1px solid rgba(248,113,113,0.3)",
                }}
              >
                {data.sybil_agents_detected} sybil{data.sybil_agents_detected !== 1 ? "s" : ""} detected
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Explainer */}
      <div className="px-6 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <div className="grid grid-cols-2 gap-4">
          <div
            className="rounded-lg p-3"
            style={{ background: "rgba(248,113,113,0.06)", border: "1px solid rgba(248,113,113,0.15)" }}
          >
            <div className="text-xs font-semibold mb-1" style={{ color: "#f87171" }}>
              Naive Ranking
            </div>
            <p className="text-xs" style={{ color: "#94a3b8" }}>
              Raw feedback scores without wallet analysis. Vulnerable to coordinated rating manipulation by sybil
              networks.
            </p>
          </div>
          <div
            className="rounded-lg p-3"
            style={{ background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.15)" }}
          >
            <div className="text-xs font-semibold mb-1" style={{ color: "#4ade80" }}>
              Sybil-Resistant
            </div>
            <p className="text-xs" style={{ color: "#94a3b8" }}>
              Weighted by wallet age, tx history, and ERC-8004 stake. Sybil feedback accounts carry near-zero weight.
            </p>
          </div>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="px-6 py-4 space-y-1">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)}
        </div>
      ) : !data ? (
        <div className="px-6 py-8 text-center" style={{ color: "#64748b" }}>
          <div className="text-2xl mb-2">⚠️</div>
          <p className="text-sm">No ranking comparison data available.</p>
          <p className="text-xs mt-1">Make sure the backend is running and feedback data is loaded.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                {["Agent", "Naive Rank", "Sybil-Safe Rank", "Rank Change", "Naive Score", "Safe Score", "Status"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider"
                      style={{ color: "#64748b" }}
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {data.agents.map((agent, idx) => {
                const isSybil = agent.flagged_as_sybil;
                return (
                  <motion.tr
                    key={agent.agent_id}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: idx * 0.05 }}
                    style={{
                      borderBottom: "1px solid rgba(255,255,255,0.04)",
                      background: isSybil ? "rgba(248,113,113,0.04)" : "transparent",
                    }}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {isSybil && (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded"
                            style={{ background: "rgba(248,113,113,0.15)", color: "#f87171" }}
                          >
                            SYBIL
                          </span>
                        )}
                        <span className="text-sm font-medium" style={{ color: isSybil ? "#f87171" : "#e2e8f0" }}>
                          {getName(agent.agent_id)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm" style={{ color: "#94a3b8" }}>
                        #{agent.naive_rank}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm font-semibold" style={{ color: "#4ade80" }}>
                        #{agent.sybil_rank}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <RankDelta delta={agent.rank_delta} />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-mono"
                        style={{ color: "#f87171", fontFamily: "JetBrains Mono, monospace" }}
                      >
                        {agent.naive_score.toFixed(3)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-mono"
                        style={{ color: "#4ade80", fontFamily: "JetBrains Mono, monospace" }}
                      >
                        {agent.sybil_resistant_score.toFixed(3)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {isSybil ? (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full"
                          style={{
                            background: "rgba(248,113,113,0.15)",
                            color: "#f87171",
                            border: "1px solid rgba(248,113,113,0.3)",
                          }}
                        >
                          Penalized
                        </span>
                      ) : (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full"
                          style={{
                            background: "rgba(74,222,128,0.1)",
                            color: "#4ade80",
                            border: "1px solid rgba(74,222,128,0.2)",
                          }}
                        >
                          Trusted
                        </span>
                      )}
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div
        className="px-6 py-3 text-xs flex items-center justify-between"
        style={{ borderTop: "1px solid rgba(255,255,255,0.05)", color: "#64748b" }}
      >
        <span>Sybil resistance via ERC-8004 wallet stake analysis</span>
        {data && (
          <span>
            Showing top 12 + 3 dramatic drops · {data.total_agents.toLocaleString()} agents evaluated
          </span>
        )}
      </div>
    </div>
  );
}
