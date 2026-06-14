"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Agent } from "@/lib/api";

export type HireState =
  | "idle"
  | "discovering"
  | "filtering"
  | "selecting"
  | "deciding"
  | "paying"
  | "serving"
  | "complete"
  | "blocked";

interface AgentNetworkProps {
  agents: Agent[];
  hireState: HireState;
  selectedAgentId?: string;
  eligibleAgentIds?: string[];
  transactionType?: "batch" | "scheduled" | "atomic_swap" | "standard";
}

const HUB_STATES: Record<HireState, string> = {
  idle: "READY",
  discovering: "SCANNING",
  filtering: "FILTERING",
  selecting: "SELECTED",
  deciding: "REASONING",
  paying: "PAYING",
  serving: "SERVING",
  complete: "DONE",
  blocked: "BLOCKED",
};

const TX_BADGES: Record<string, { label: string; color: string }> = {
  batch: { label: "⚡ BATCH", color: "#6c63ff" },
  scheduled: { label: "⏰ SCHED", color: "#f59e0b" },
  atomic_swap: { label: "↔ SWAP", color: "#3ecfcf" },
  standard: { label: "STD", color: "#94a3b8" },
};

const AGENT_CYS = [110, 200, 290, 380, 460];

// Path data for connections
const PATHS = {
  reqToHub: "M 152,280 C 310,280 310,280 412,280",
  hubToAgents: [
    "M 588,280 C 720,280 720,110 838,110",
    "M 588,270 C 720,260 720,200 838,200",
    "M 590,280 C 720,280 720,290 838,290",
    "M 588,290 C 720,300 720,380 838,380",
    "M 588,300 C 720,320 720,460 838,460",
  ],
};

function truncateName(name: string, maxLen = 14): string {
  return name.length > maxLen ? name.slice(0, maxLen - 1) + "…" : name;
}

export default function AgentNetwork({
  agents,
  hireState,
  selectedAgentId,
  eligibleAgentIds,
  transactionType = "standard",
}: AgentNetworkProps) {
  const displayAgents = agents.slice(0, 5);
  const hubLabel = HUB_STATES[hireState] || "READY";
  const txBadge = TX_BADGES[transactionType] || TX_BADGES.standard;

  const isActive = hireState !== "idle";
  const isComplete = hireState === "complete";
  const isBlocked = hireState === "blocked";
  const isPaying = hireState === "paying";
  const isServing = hireState === "serving";
  const isDiscovering = hireState === "discovering";

  function getAgentOpacity(idx: number): number {
    if (!displayAgents[idx]) return 0.2;
    const agent = displayAgents[idx];

    if (hireState === "idle") return 0.4;
    if (hireState === "discovering") return 1;
    if (hireState === "filtering") {
      if (!eligibleAgentIds || eligibleAgentIds.length === 0) return 0.7;
      return eligibleAgentIds.includes(agent.agent_id) ? 1 : 0.2;
    }
    if (hireState === "selecting" || hireState === "deciding" || hireState === "paying" || hireState === "serving") {
      return agent.agent_id === selectedAgentId ? 1 : 0.2;
    }
    if (hireState === "complete") return agent.agent_id === selectedAgentId ? 1 : 0.3;
    if (hireState === "blocked") return 0.2;
    return 0.7;
  }

  function getLineOpacity(idx: number): number {
    if (hireState === "idle") return 0.15;
    if (isDiscovering) return 0.8;
    if (hireState === "filtering") {
      if (!eligibleAgentIds || eligibleAgentIds.length === 0) return 0.5;
      const agent = displayAgents[idx];
      return agent && eligibleAgentIds.includes(agent.agent_id) ? 0.8 : 0.1;
    }
    if (["selecting", "deciding", "paying", "serving", "complete"].includes(hireState)) {
      const agent = displayAgents[idx];
      return agent && agent.agent_id === selectedAgentId ? 1 : 0.08;
    }
    if (isBlocked) return 0.1;
    return 0.4;
  }

  function getLineWidth(idx: number): number {
    const agent = displayAgents[idx];
    if (agent && agent.agent_id === selectedAgentId) return 2.5;
    return 1.5;
  }

  function getLineStroke(idx: number): string {
    const agent = displayAgents[idx];
    if (isComplete && agent?.agent_id === selectedAgentId) return "#4ade80";
    if (isBlocked) return "#f87171";
    if (agent?.agent_id === selectedAgentId) return "#6c63ff";
    if (isDiscovering) return "#3ecfcf";
    return "#6c63ff";
  }

  const hubGlowColor = isComplete ? "#4ade80" : isBlocked ? "#f87171" : "#6c63ff";
  const reqLineColor = isActive ? "#3ecfcf" : "#3ecfcf";

  return (
    <div className="relative w-full" style={{ aspectRatio: "1000/560" }}>
      <svg
        viewBox="0 0 1000 560"
        className="w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          {/* Purple gradient */}
          <linearGradient id="purpleGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6c63ff" />
            <stop offset="100%" stopColor="#3ecfcf" />
          </linearGradient>
          {/* Green gradient for complete */}
          <linearGradient id="greenGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#4ade80" />
            <stop offset="100%" stopColor="#3ecfcf" />
          </linearGradient>
          {/* Glow filters */}
          <filter id="glow-purple">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-cyan">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-green">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Path definitions for animateMotion */}
          <path id="path-req-to-hub" d={PATHS.reqToHub} />
          {PATHS.hubToAgents.map((d, i) => (
            <path key={i} id={`path-hub-to-agent-${i}`} d={d} />
          ))}
          {/* Reverse paths for serve state */}
          {PATHS.hubToAgents.map((_, i) => {
            const selectedIdx = displayAgents.findIndex((a) => a.agent_id === selectedAgentId);
            if (i !== selectedIdx) return null;
            return <path key={`rev-${i}`} id={`path-agent-to-hub-${i}`} d={PATHS.hubToAgents[i]} />;
          })}
        </defs>

        {/* Background subtle glow at hub */}
        <circle
          cx="500"
          cy="280"
          r="140"
          fill="none"
          style={{
            fill: `radial-gradient(circle, ${hubGlowColor}10 0%, transparent 70%)`,
            opacity: isActive ? 0.3 : 0.1,
          }}
        />
        <radialGradient id="hubBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={hubGlowColor} stopOpacity="0.08" />
          <stop offset="100%" stopColor="transparent" stopOpacity="0" />
        </radialGradient>
        <circle cx="500" cy="280" r="160" fill="url(#hubBg)" />

        {/* ─── CONNECTION LINES ─────────────────────────────────────── */}

        {/* Requester → Hub */}
        <motion.path
          d={PATHS.reqToHub}
          fill="none"
          strokeWidth="1.5"
          strokeDasharray={isActive ? "none" : "4 8"}
          animate={{
            stroke: isComplete ? "#4ade80" : isBlocked ? "#f87171" : "#3ecfcf",
            opacity: isActive ? 0.9 : 0.2,
            strokeWidth: isActive ? 2 : 1.5,
          }}
          transition={{ duration: 0.4 }}
        />

        {/* Hub → Agent lines */}
        {PATHS.hubToAgents.map((d, idx) => (
          <motion.path
            key={`line-${idx}`}
            id={`visible-hub-to-agent-${idx}`}
            d={d}
            fill="none"
            strokeDasharray={hireState === "idle" ? "4 8" : "none"}
            animate={{
              stroke: getLineStroke(idx),
              opacity: getLineOpacity(idx),
              strokeWidth: getLineWidth(idx),
            }}
            transition={{ duration: 0.5, delay: idx * 0.05 }}
          />
        ))}

        {/* ─── PARTICLES (animateMotion) ──────────────────────────── */}

        {/* Payment: Requester → Hub */}
        {isPaying && (
          <>
            <circle r="5" fill="#3ecfcf" opacity="0.9" filter="url(#glow-cyan)">
              <animateMotion dur="1.2s" repeatCount="indefinite" begin="0s">
                <mpath href="#path-req-to-hub" />
              </animateMotion>
            </circle>
            <circle r="3" fill="#3ecfcf" opacity="0.6">
              <animateMotion dur="1.2s" repeatCount="indefinite" begin="0.4s">
                <mpath href="#path-req-to-hub" />
              </animateMotion>
            </circle>
          </>
        )}

        {/* Pay signal: Hub → Selected Agent */}
        {isPaying &&
          displayAgents.map((agent, idx) =>
            agent.agent_id === selectedAgentId ? (
              <circle key={`pay-signal-${idx}`} r="5" fill="#6c63ff" opacity="0.9" filter="url(#glow-purple)">
                <animateMotion dur="1.4s" repeatCount="indefinite" begin="0.2s">
                  <mpath href={`#path-hub-to-agent-${idx}`} />
                </animateMotion>
              </circle>
            ) : null
          )}

        {/* Serve: Selected Agent → Hub → Requester */}
        {isServing &&
          displayAgents.map((agent, idx) =>
            agent.agent_id === selectedAgentId ? (
              <g key={`serve-particles-${idx}`}>
                <circle r="5" fill="#4ade80" opacity="0.9" filter="url(#glow-green)">
                  <animateMotion dur="1.5s" repeatCount="indefinite" begin="0s" keyPoints="1;0" keyTimes="0;1" calcMode="linear">
                    <mpath href={`#path-hub-to-agent-${idx}`} />
                  </animateMotion>
                </circle>
                <circle r="4" fill="#4ade80" opacity="0.7">
                  <animateMotion dur="1.2s" repeatCount="indefinite" begin="0.3s" keyPoints="1;0" keyTimes="0;1" calcMode="linear">
                    <mpath href="#path-req-to-hub" />
                  </animateMotion>
                </circle>
              </g>
            ) : null
          )}

        {/* Discover: animated along all lines */}
        {isDiscovering &&
          PATHS.hubToAgents.map((_, idx) => (
            <circle key={`disc-${idx}`} r="4" fill="#3ecfcf" opacity="0.8">
              <animateMotion dur="1.8s" repeatCount="indefinite" begin={`${idx * 0.2}s`}>
                <mpath href={`#path-hub-to-agent-${idx}`} />
              </animateMotion>
            </circle>
          ))}

        {/* ─── REQUESTER NODE ────────────────────────────────────── */}
        <motion.g
          animate={{ opacity: isBlocked ? 0.5 : 1 }}
          transition={{ duration: 0.3 }}
        >
          {/* Outer glow ring */}
          <motion.circle
            cx="110"
            cy="280"
            r="52"
            fill="none"
            stroke="#3ecfcf"
            strokeWidth="1"
            animate={{
              opacity: isActive ? [0.3, 0.6, 0.3] : 0.15,
              r: isActive ? [52, 58, 52] : 52,
            }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          />
          {/* Hexagon */}
          <polygon
            points="110,242 148,262 148,298 110,318 72,298 72,262"
            fill="rgba(62,207,207,0.08)"
            stroke="#3ecfcf"
            strokeWidth="1.5"
            filter="url(#glow-cyan)"
          />
          {/* Inner icon */}
          <text x="110" y="276" textAnchor="middle" fill="#3ecfcf" fontSize="18" fontWeight="600">
            🤖
          </text>
          <text x="110" y="292" textAnchor="middle" fill="#94a3b8" fontSize="8" fontFamily="JetBrains Mono, monospace">
            REQ-v1
          </text>
          {/* Label below */}
          <text x="110" y="334" textAnchor="middle" fill="#94a3b8" fontSize="10" fontWeight="500">
            Requester
          </text>
          <text x="110" y="346" textAnchor="middle" fill="#94a3b8" fontSize="10" fontWeight="500">
            Agent
          </text>
        </motion.g>

        {/* ─── HUB NODE ──────────────────────────────────────────── */}
        <g>
          {/* Pulsing rings */}
          <motion.circle
            cx="500"
            cy="280"
            r="100"
            fill="none"
            stroke={hubGlowColor}
            strokeWidth="1"
            animate={{
              opacity: [0.15, 0.35, 0.15],
              r: [100, 108, 100],
            }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.circle
            cx="500"
            cy="280"
            r="115"
            fill="none"
            stroke={hubGlowColor}
            strokeWidth="0.5"
            animate={{
              opacity: [0.08, 0.2, 0.08],
              r: [115, 124, 115],
            }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
          />

          {/* Main hexagon */}
          <motion.polygon
            points="500,196 576,238 576,322 500,364 424,322 424,238"
            fill="rgba(108,99,255,0.08)"
            animate={{
              stroke: hubGlowColor,
              filter: isComplete
                ? "drop-shadow(0 0 16px #4ade80)"
                : isBlocked
                ? "drop-shadow(0 0 16px #f87171)"
                : "drop-shadow(0 0 12px #6c63ff)",
            }}
            strokeWidth="2"
            transition={{ duration: 0.4 }}
            filter="url(#glow-purple)"
          />

          {/* Inner hex */}
          <polygon
            points="500,220 554,250 554,310 500,340 446,310 446,250"
            fill="rgba(108,99,255,0.05)"
            stroke="rgba(108,99,255,0.3)"
            strokeWidth="1"
          />

          {/* Hub status text */}
          <AnimatePresence mode="wait">
            <motion.g key={hireState}>
              <motion.text
                x="500"
                y="268"
                textAnchor="middle"
                fill={hubGlowColor}
                fontSize="13"
                fontWeight="800"
                fontFamily="JetBrains Mono, monospace"
                letterSpacing="2"
                initial={{ opacity: 0, y: 275 }}
                animate={{ opacity: 1, y: 268 }}
                exit={{ opacity: 0, y: 261 }}
                transition={{ duration: 0.25 }}
              >
                {isComplete ? "✓" : isBlocked ? "✗" : "⬡"}
              </motion.text>
              <motion.text
                x="500"
                y="284"
                textAnchor="middle"
                fill="#e2e8f0"
                fontSize="11"
                fontWeight="700"
                fontFamily="JetBrains Mono, monospace"
                letterSpacing="1.5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25, delay: 0.05 }}
              >
                {hubLabel}
              </motion.text>
            </motion.g>
          </AnimatePresence>

          {/* Transaction type badge */}
          {transactionType && transactionType !== "standard" && (
            <g>
              <rect
                x="460"
                y="296"
                width="80"
                height="18"
                rx="9"
                fill={`${txBadge.color}20`}
                stroke={txBadge.color}
                strokeWidth="1"
              />
              <text
                x="500"
                y="308"
                textAnchor="middle"
                fill={txBadge.color}
                fontSize="8"
                fontWeight="700"
                fontFamily="JetBrains Mono, monospace"
                letterSpacing="0.5"
              >
                {txBadge.label}
              </text>
            </g>
          )}

          {/* AGENTRANKER label below hex */}
          <text x="500" y="384" textAnchor="middle" fill="#6c63ff" fontSize="11" fontWeight="700" letterSpacing="2">
            AGENTRANKER
          </text>
          <text x="500" y="396" textAnchor="middle" fill="#94a3b8" fontSize="8" letterSpacing="1">
            Trust Layer
          </text>
        </g>

        {/* ─── AGENT NODES ───────────────────────────────────────── */}
        {displayAgents.map((agent, idx) => {
          const cy = AGENT_CYS[idx];
          const opacity = getAgentOpacity(idx);
          const isSelected = agent.agent_id === selectedAgentId;
          const score = agent.trust_score;
          const barWidth = Math.round(score * 60);
          const glowColor = isComplete && isSelected ? "#4ade80" : isSelected ? "#6c63ff" : "#3ecfcf";

          return (
            <motion.g
              key={agent.agent_id}
              animate={{ opacity }}
              transition={{ duration: 0.4, delay: idx * 0.06 }}
            >
              {/* Selection ring */}
              {isSelected && (hireState === "selecting" || hireState === "deciding" || hireState === "paying" || hireState === "serving" || hireState === "complete") && (
                <motion.circle
                  cx="870"
                  cy={cy}
                  r="42"
                  fill="none"
                  stroke={glowColor}
                  strokeWidth="1.5"
                  animate={{
                    opacity: [0.4, 0.8, 0.4],
                    r: [42, 48, 42],
                  }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
              )}

              {/* Agent circle */}
              <circle
                cx="870"
                cy={cy}
                r="32"
                fill="rgba(108,99,255,0.06)"
                stroke={isSelected ? glowColor : "#6c63ff"}
                strokeWidth={isSelected ? 2 : 1}
                filter={isSelected ? "url(#glow-purple)" : undefined}
              />

              {/* Rank badge */}
              <circle cx="848" cy={cy - 20} r="9" fill={isSelected ? "#6c63ff" : "#1a1a2e"} stroke="#6c63ff" strokeWidth="1" />
              <text x="848" y={cy - 16} textAnchor="middle" fill="#e2e8f0" fontSize="8" fontWeight="700">
                #{idx + 1}
              </text>

              {/* Agent name */}
              <text
                x="870"
                y={cy - 8}
                textAnchor="middle"
                fill={isSelected ? "#e2e8f0" : "#94a3b8"}
                fontSize="8"
                fontWeight={isSelected ? "700" : "500"}
              >
                {truncateName(agent.name, 13)}
              </text>

              {/* Trust score */}
              <text
                x="870"
                y={cy + 4}
                textAnchor="middle"
                fill={isSelected ? glowColor : "#6c63ff"}
                fontSize="10"
                fontWeight="700"
                fontFamily="JetBrains Mono, monospace"
              >
                {score.toFixed(3)}
              </text>

              {/* Mini trust bar */}
              <rect x={870 - 30} y={cy + 8} width="60" height="3" rx="1.5" fill="rgba(255,255,255,0.08)" />
              <rect x={870 - 30} y={cy + 8} width={barWidth} height="3" rx="1.5" fill={isSelected ? glowColor : "#6c63ff"} />

              {/* x402 badge */}
              {agent.supports_x402 && (
                <g>
                  <rect x="850" y={cy + 14} width="38" height="10" rx="5" fill="rgba(62,207,207,0.15)" stroke="#3ecfcf" strokeWidth="0.5" />
                  <text x="869" y={cy + 22} textAnchor="middle" fill="#3ecfcf" fontSize="6" fontWeight="600">
                    x402
                  </text>
                </g>
              )}
            </motion.g>
          );
        })}

        {/* Placeholder agent nodes if fewer than 5 */}
        {Array.from({ length: Math.max(0, 5 - displayAgents.length) }).map((_, idx) => {
          const realIdx = displayAgents.length + idx;
          const cy = AGENT_CYS[realIdx];
          return (
            <g key={`placeholder-${idx}`} opacity={0.15}>
              <circle cx="870" cy={cy} r="32" fill="none" stroke="#6c63ff" strokeWidth="1" strokeDasharray="4 4" />
              <text x="870" y={cy + 4} textAnchor="middle" fill="#6c63ff" fontSize="9">
                Agent
              </text>
            </g>
          );
        })}

        {/* ─── LABELS ─────────────────────────────────────────────── */}
        <text x="870" y="510" textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="500">
          Agent Network
        </text>
        <text x="110" y="510" textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="500">
          Requester
        </text>
        <text x="500" y="510" textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="500">
          Trust Hub
        </text>
      </svg>
    </div>
  );
}
