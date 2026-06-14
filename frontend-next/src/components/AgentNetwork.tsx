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

// Compressed layout: all 5 agents + hub fit within ~340 SVG units vertically
const AGENT_CYS = [60, 125, 190, 255, 310];

// Hub center at y=185, outer hex radius=55, inner radius=38
// Req center at x=110, y=185
const PATHS = {
  reqToHub:    "M 143,185 C 310,185 310,185 452,185",
  hubToAgents: [
    "M 548,185 C 700,185 720,60  848,60",
    "M 548,178 C 700,160 720,125 848,125",
    "M 548,185 C 700,185 720,190 848,190",
    "M 548,192 C 700,210 720,255 848,255",
    "M 548,200 C 700,235 720,310 848,310",
  ],
};

function truncateName(name: string, maxLen = 13): string {
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

  const isActive      = hireState !== "idle";
  const isComplete    = hireState === "complete";
  const isBlocked     = hireState === "blocked";
  const isPaying      = hireState === "paying";
  const isServing     = hireState === "serving";
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
    if (["selecting","deciding","paying","serving"].includes(hireState))
      return agent.agent_id === selectedAgentId ? 1 : 0.2;
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
    if (["selecting","deciding","paying","serving","complete"].includes(hireState)) {
      const agent = displayAgents[idx];
      return agent && agent.agent_id === selectedAgentId ? 1 : 0.08;
    }
    if (isBlocked) return 0.1;
    return 0.4;
  }

  function getLineWidth(idx: number): number {
    return displayAgents[idx]?.agent_id === selectedAgentId ? 2.5 : 1.5;
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

  return (
    <div className="relative w-full" style={{ aspectRatio: "1000/420" }}>
      <svg viewBox="0 0 1000 420" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="purpleGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6c63ff" />
            <stop offset="100%" stopColor="#3ecfcf" />
          </linearGradient>
          <linearGradient id="greenGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#4ade80" />
            <stop offset="100%" stopColor="#3ecfcf" />
          </linearGradient>
          <filter id="glow-purple">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow-cyan">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow-green">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <radialGradient id="hubBg" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={hubGlowColor} stopOpacity="0.08" />
            <stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </radialGradient>

          {/* Path defs for animateMotion */}
          <path id="path-req-to-hub" d={PATHS.reqToHub} />
          {PATHS.hubToAgents.map((d, i) => (
            <path key={i} id={`path-hub-to-agent-${i}`} d={d} />
          ))}
          {PATHS.hubToAgents.map((_, i) => {
            const selectedIdx = displayAgents.findIndex((a) => a.agent_id === selectedAgentId);
            if (i !== selectedIdx) return null;
            return <path key={`rev-${i}`} id={`path-agent-to-hub-${i}`} d={PATHS.hubToAgents[i]} />;
          })}
        </defs>

        {/* Hub background glow */}
        <circle cx="500" cy="185" r="100" fill="url(#hubBg)" />

        {/* ─── CONNECTION LINES ─────────────────────────────────── */}

        {/* Requester → Hub */}
        <motion.path
          d={PATHS.reqToHub}
          fill="none"
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

        {/* ─── PARTICLES ─────────────────────────────────────────── */}

        {isPaying && (
          <>
            <circle r="4" fill="#3ecfcf" opacity="0.9" filter="url(#glow-cyan)">
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

        {isPaying && displayAgents.map((agent, idx) =>
          agent.agent_id === selectedAgentId ? (
            <circle key={`pay-${idx}`} r="4" fill="#6c63ff" opacity="0.9" filter="url(#glow-purple)">
              <animateMotion dur="1.4s" repeatCount="indefinite" begin="0.2s">
                <mpath href={`#path-hub-to-agent-${idx}`} />
              </animateMotion>
            </circle>
          ) : null
        )}

        {isServing && displayAgents.map((agent, idx) =>
          agent.agent_id === selectedAgentId ? (
            <g key={`serve-${idx}`}>
              <circle r="4" fill="#4ade80" opacity="0.9" filter="url(#glow-green)">
                <animateMotion dur="1.5s" repeatCount="indefinite" begin="0s" keyPoints="1;0" keyTimes="0;1" calcMode="linear">
                  <mpath href={`#path-hub-to-agent-${idx}`} />
                </animateMotion>
              </circle>
              <circle r="3" fill="#4ade80" opacity="0.7">
                <animateMotion dur="1.2s" repeatCount="indefinite" begin="0.3s" keyPoints="1;0" keyTimes="0;1" calcMode="linear">
                  <mpath href="#path-req-to-hub" />
                </animateMotion>
              </circle>
            </g>
          ) : null
        )}

        {isDiscovering && PATHS.hubToAgents.map((_, idx) => (
          <circle key={`disc-${idx}`} r="3" fill="#3ecfcf" opacity="0.8">
            <animateMotion dur="1.8s" repeatCount="indefinite" begin={`${idx * 0.2}s`}>
              <mpath href={`#path-hub-to-agent-${idx}`} />
            </animateMotion>
          </circle>
        ))}

        {/* ─── REQUESTER NODE ────────────────────────────────────── */}
        <motion.g animate={{ opacity: isBlocked ? 0.5 : 1 }} transition={{ duration: 0.3 }}>
          <motion.circle
            cx="110" cy="185" r="46"
            fill="none" stroke="#3ecfcf" strokeWidth="1"
            animate={{
              opacity: isActive ? [0.3, 0.6, 0.3] : 0.15,
              r: isActive ? [46, 52, 46] : 46,
            }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          />
          {/* Requester hexagon */}
          <polygon
            points="110,147 143,166 143,204 110,223 77,204 77,166"
            fill="rgba(62,207,207,0.08)"
            stroke="#3ecfcf"
            strokeWidth="1.5"
            filter="url(#glow-cyan)"
          />
          <text x="110" y="181" textAnchor="middle" fill="#3ecfcf" fontSize="16" fontWeight="600">🤖</text>
          <text x="110" y="196" textAnchor="middle" fill="#94a3b8" fontSize="7" fontFamily="JetBrains Mono, monospace">REQ-v1</text>
          <text x="110" y="238" textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="500">Requester</text>
          <text x="110" y="249" textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="500">Agent</text>
        </motion.g>

        {/* ─── HUB NODE ──────────────────────────────────────────── */}
        <g>
          {/* Pulsing rings */}
          <motion.circle
            cx="500" cy="185" r="72"
            fill="none" stroke={hubGlowColor} strokeWidth="1"
            animate={{ opacity: [0.15, 0.35, 0.15], r: [72, 79, 72] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.circle
            cx="500" cy="185" r="83"
            fill="none" stroke={hubGlowColor} strokeWidth="0.5"
            animate={{ opacity: [0.08, 0.2, 0.08], r: [83, 91, 83] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
          />

          {/* Outer hexagon */}
          <motion.polygon
            points="500,130 548,158 548,213 500,240 452,213 452,158"
            fill="rgba(108,99,255,0.08)"
            animate={{
              stroke: hubGlowColor,
              filter: isComplete
                ? "drop-shadow(0 0 14px #4ade80)"
                : isBlocked
                ? "drop-shadow(0 0 14px #f87171)"
                : "drop-shadow(0 0 10px #6c63ff)",
            }}
            strokeWidth="2"
            transition={{ duration: 0.4 }}
            filter="url(#glow-purple)"
          />

          {/* Inner hexagon */}
          <polygon
            points="500,147 533,166 533,204 500,221 467,204 467,166"
            fill="rgba(108,99,255,0.05)"
            stroke="rgba(108,99,255,0.3)"
            strokeWidth="1"
          />

          {/* Hub status text */}
          <AnimatePresence mode="wait">
            <motion.g key={hireState}>
              <motion.text
                x="500" y="181"
                textAnchor="middle"
                fill={hubGlowColor}
                fontSize="12" fontWeight="800"
                fontFamily="JetBrains Mono, monospace"
                letterSpacing="2"
                initial={{ opacity: 0, y: 186 }}
                animate={{ opacity: 1, y: 181 }}
                exit={{ opacity: 0, y: 176 }}
                transition={{ duration: 0.25 }}
              >
                {isComplete ? "✓" : isBlocked ? "✗" : "⬡"}
              </motion.text>
              <motion.text
                x="500" y="195"
                textAnchor="middle"
                fill="#e2e8f0"
                fontSize="10" fontWeight="700"
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

          {/* TX type badge */}
          {transactionType && transactionType !== "standard" && (
            <g>
              <rect x="460" y="210" width="80" height="16" rx="8"
                fill={`${txBadge.color}20`} stroke={txBadge.color} strokeWidth="1" />
              <text x="500" y="221" textAnchor="middle"
                fill={txBadge.color} fontSize="7" fontWeight="700"
                fontFamily="JetBrains Mono, monospace" letterSpacing="0.5">
                {txBadge.label}
              </text>
            </g>
          )}

          <text x="500" y="258" textAnchor="middle" fill="#6c63ff" fontSize="9" fontWeight="700" letterSpacing="2">AGENTRANKER</text>
          <text x="500" y="268" textAnchor="middle" fill="#94a3b8" fontSize="7" letterSpacing="1">Trust Layer</text>
        </g>

        {/* ─── AGENT NODES ───────────────────────────────────────── */}
        {displayAgents.map((agent, idx) => {
          const cy = AGENT_CYS[idx];
          const opacity = getAgentOpacity(idx);
          const isSelected = agent.agent_id === selectedAgentId;
          const score = agent.trust_score;
          const barWidth = Math.round(score * 44);
          const glowColor = isComplete && isSelected ? "#4ade80" : isSelected ? "#6c63ff" : "#3ecfcf";

          return (
            <motion.g
              key={agent.agent_id}
              animate={{ opacity }}
              transition={{ duration: 0.4, delay: idx * 0.06 }}
            >
              {/* Selection ring */}
              {isSelected && ["selecting","deciding","paying","serving","complete"].includes(hireState) && (
                <motion.circle
                  cx="870" cy={cy} r="32"
                  fill="none" stroke={glowColor} strokeWidth="1.5"
                  animate={{ opacity: [0.4, 0.8, 0.4], r: [32, 38, 32] }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
              )}

              {/* Agent circle */}
              <circle
                cx="870" cy={cy} r="22"
                fill="rgba(108,99,255,0.06)"
                stroke={isSelected ? glowColor : "#6c63ff"}
                strokeWidth={isSelected ? 2 : 1}
                filter={isSelected ? "url(#glow-purple)" : undefined}
              />

              {/* Rank badge */}
              <circle cx="856" cy={cy - 16} r="8"
                fill={isSelected ? "#6c63ff" : "#1a1a2e"}
                stroke="#6c63ff" strokeWidth="1" />
              <text x="856" y={cy - 12} textAnchor="middle" fill="#e2e8f0" fontSize="7" fontWeight="700">
                #{idx + 1}
              </text>

              {/* Agent name */}
              <text x="870" y={cy - 7} textAnchor="middle"
                fill={isSelected ? "#e2e8f0" : "#94a3b8"}
                fontSize="7" fontWeight={isSelected ? "700" : "500"}>
                {truncateName(agent.name)}
              </text>

              {/* Trust score */}
              <text x="870" y={cy + 5} textAnchor="middle"
                fill={isSelected ? glowColor : "#6c63ff"}
                fontSize="9" fontWeight="700"
                fontFamily="JetBrains Mono, monospace">
                {score.toFixed(3)}
              </text>

              {/* Trust bar */}
              <rect x={848} y={cy + 9} width="44" height="3" rx="1.5" fill="rgba(255,255,255,0.08)" />
              <rect x={848} y={cy + 9} width={barWidth} height="3" rx="1.5"
                fill={isSelected ? glowColor : "#6c63ff"} />

              {/* x402 badge */}
              {agent.supports_x402 && (
                <g>
                  <rect x="852" y={cy + 14} width="34" height="9" rx="4.5"
                    fill="rgba(62,207,207,0.15)" stroke="#3ecfcf" strokeWidth="0.5" />
                  <text x="869" y={cy + 21} textAnchor="middle"
                    fill="#3ecfcf" fontSize="6" fontWeight="600">x402</text>
                </g>
              )}
            </motion.g>
          );
        })}

        {/* Placeholder agents */}
        {Array.from({ length: Math.max(0, 5 - displayAgents.length) }).map((_, idx) => {
          const realIdx = displayAgents.length + idx;
          const cy = AGENT_CYS[realIdx];
          return (
            <g key={`placeholder-${idx}`} opacity={0.15}>
              <circle cx="870" cy={cy} r="22" fill="none" stroke="#6c63ff" strokeWidth="1" strokeDasharray="4 4" />
              <text x="870" y={cy + 4} textAnchor="middle" fill="#6c63ff" fontSize="8">Agent</text>
            </g>
          );
        })}

        {/* ─── FOOTER LABELS ─────────────────────────────────────── */}
        <text x="110" y="395" textAnchor="middle" fill="#94a3b8" fontSize="8" fontWeight="500">Requester</text>
        <text x="500" y="395" textAnchor="middle" fill="#94a3b8" fontSize="8" fontWeight="500">Trust Hub</text>
        <text x="870" y="395" textAnchor="middle" fill="#94a3b8" fontSize="8" fontWeight="500">Agent Network</text>
      </svg>
    </div>
  );
}
