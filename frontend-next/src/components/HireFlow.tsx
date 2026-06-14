"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { HireStep } from "@/lib/api";

interface HireFlowProps {
  steps: HireStep[];
  isRunning: boolean;
}

const STEP_ICONS: Record<string, string> = {
  discover: "🔍",
  filter: "🔎",
  select: "🏆",
  decide: "🧠",
  pay: "💸",
  serve: "✅",
};

const STATUS_COLORS = {
  ok: "#4ade80",
  blocked: "#f59e0b",
  error: "#f87171",
};

function TxTypeBadge({ data }: { data: Record<string, unknown> }) {
  const txType = data?.transaction_type as string | undefined;
  if (!txType || txType === "standard") return null;

  const badges: Record<string, { label: string; color: string; bg: string; icon: string }> = {
    batch: {
      label: "HIP-551 BATCH",
      color: "#a5b4fc",
      bg: "rgba(108,99,255,0.15)",
      icon: "⚡",
    },
    scheduled: {
      label: "SCHEDULED",
      color: "#fcd34d",
      bg: "rgba(245,158,11,0.15)",
      icon: "⏰",
    },
    atomic_swap: {
      label: "ATOMIC SWAP",
      color: "#67e8f9",
      bg: "rgba(62,207,207,0.15)",
      icon: "↔",
    },
  };

  const badge = badges[txType];
  if (!badge) return null;

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold"
      style={{ background: badge.bg, color: badge.color, border: `1px solid ${badge.color}40` }}
    >
      <span>{badge.icon}</span>
      {badge.label}
    </span>
  );
}

function StepBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status as keyof typeof STATUS_COLORS] || "#94a3b8";
  const label = { ok: "OK", blocked: "BLOCKED", error: "ERROR" }[status] || status.toUpperCase();

  return (
    <span
      className="text-xs font-bold px-2 py-0.5 rounded-full"
      style={{
        background: `${color}20`,
        color,
        border: `1px solid ${color}40`,
      }}
    >
      {label}
    </span>
  );
}

function HashScanLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={`View on HashScan: ${label}`}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold transition-all duration-150"
      style={{
        background: "rgba(108,99,255,0.12)",
        color: "#a5b4fc",
        border: "1px solid rgba(108,99,255,0.3)",
        textDecoration: "none",
      }}
      onMouseOver={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.background = "rgba(108,99,255,0.25)";
        (e.currentTarget as HTMLAnchorElement).style.borderColor = "rgba(108,99,255,0.6)";
      }}
      onMouseOut={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.background = "rgba(108,99,255,0.12)";
        (e.currentTarget as HTMLAnchorElement).style.borderColor = "rgba(108,99,255,0.3)";
      }}
    >
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M1 9L9 1M9 1H4M9 1V6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
      HashScan
    </a>
  );
}

function txHashScanUrl(txId: string): string {
  return `https://hashscan.io/testnet/transaction/${txId}`;
}

function hcsHashScanUrl(hcsMessageId: string): string {
  // hcs_message_id format: "0.0.TOPIC_NUM/SEQ_NUM"
  const topicId = hcsMessageId.split("/")[0];
  return `https://hashscan.io/testnet/topic/${topicId}`;
}

function SpinnerDot({ color }: { color: string }) {
  return (
    <motion.div
      className="w-3 h-3 rounded-full flex-shrink-0"
      style={{ background: color, boxShadow: `0 0 8px ${color}` }}
      animate={{ scale: [1, 1.4, 1], opacity: [1, 0.5, 1] }}
      transition={{ duration: 1.2, repeat: Infinity }}
    />
  );
}

export default function HireFlow({ steps, isRunning }: HireFlowProps) {
  if (steps.length === 0 && !isRunning) {
    return (
      <div
        className="rounded-xl p-6 text-center"
        style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="text-4xl mb-3">⬡</div>
        <p className="text-sm" style={{ color: "#94a3b8" }}>
          Configure the form above and click <strong style={{ color: "#6c63ff" }}>Run Hire</strong> to start the
          autonomous agent hiring loop.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <AnimatePresence>
        {steps.map((step, idx) => {
          const icon = STEP_ICONS[step.step_type] || "●";
          const color = STATUS_COLORS[step.status as keyof typeof STATUS_COLORS] || "#94a3b8";
          const isPay = step.step_type === "pay";

          return (
            <motion.div
              key={`${step.step_type}-${idx}`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: idx * 0.08 }}
              className="rounded-xl overflow-hidden"
              style={{
                background: "rgba(255,255,255,0.03)",
                border: `1px solid ${step.status === "ok" ? "rgba(255,255,255,0.08)" : `${color}30`}`,
              }}
            >
              <div className="p-4">
                <div className="flex items-start gap-3">
                  {/* Step icon */}
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-base"
                    style={{
                      background: `${color}15`,
                      border: `1px solid ${color}30`,
                    }}
                  >
                    {icon}
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Title row */}
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
                        {step.title}
                      </span>
                      <StepBadge status={step.status} />
                      {isPay && <TxTypeBadge data={step.data} />}
                      <span className="text-xs ml-auto" style={{ color: "#64748b" }}>
                        {step.elapsed_ms}ms
                      </span>
                    </div>

                    {/* Description */}
                    <p className="text-xs leading-relaxed" style={{ color: "#94a3b8" }}>
                      {step.description}
                    </p>

                    {/* Pay step extra data */}
                    {isPay && step.data && (
                      <div className="mt-3 space-y-2">
                        {step.data.tx_id && (
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs" style={{ color: "#64748b" }}>Tx:</span>
                            <span
                              className="text-xs font-mono truncate"
                              style={{ color: "#a5b4fc", fontFamily: "JetBrains Mono, monospace" }}
                            >
                              {String(step.data.tx_id)}
                            </span>
                            <HashScanLink
                              href={txHashScanUrl(String(step.data.tx_id))}
                              label={String(step.data.tx_id)}
                            />
                          </div>
                        )}
                        {step.data.hcs_message_id && (
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs" style={{ color: "#64748b" }}>HCS audit:</span>
                            <span
                              className="text-xs font-mono truncate"
                              style={{ color: "#67e8f9", fontFamily: "JetBrains Mono, monospace" }}
                            >
                              {String(step.data.hcs_message_id)}
                            </span>
                            <HashScanLink
                              href={hcsHashScanUrl(String(step.data.hcs_message_id))}
                              label={`topic ${String(step.data.hcs_message_id).split("/")[0]}`}
                            />
                          </div>
                        )}
                        {step.data.batch_id && (
                          <div className="flex items-center gap-2">
                            <span className="text-xs" style={{ color: "#64748b" }}>Batch/Sched ID:</span>
                            <span
                              className="text-xs font-mono truncate"
                              style={{ color: "#fcd34d", fontFamily: "JetBrains Mono, monospace" }}
                            >
                              {String(step.data.batch_id)}
                            </span>
                          </div>
                        )}
                        {step.data.scheduled_at && (
                          <div className="flex items-center gap-2">
                            <span className="text-xs" style={{ color: "#64748b" }}>Scheduled:</span>
                            <span className="text-xs" style={{ color: "#fcd34d" }}>
                              {String(step.data.scheduled_at).replace("T", " ").replace(/\.\d+.*$/, " UTC")}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Progress indicator at bottom */}
              <div
                className="h-0.5"
                style={{
                  background: `linear-gradient(90deg, ${color}, transparent)`,
                  opacity: 0.6,
                }}
              />
            </motion.div>
          );
        })}
      </AnimatePresence>

      {/* Running indicator */}
      {isRunning && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center gap-3 px-4 py-3 rounded-xl"
          style={{ background: "rgba(108,99,255,0.08)", border: "1px solid rgba(108,99,255,0.2)" }}
        >
          <SpinnerDot color="#6c63ff" />
          <span className="text-sm" style={{ color: "#a5b4fc" }}>
            Autonomous hire loop running...
          </span>
        </motion.div>
      )}
    </div>
  );
}
