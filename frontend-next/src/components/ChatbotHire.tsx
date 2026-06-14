"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { runAutonomousHire, type HireStep } from "@/lib/api";
import type { HireState } from "./AgentNetwork";

// ── Domain catalog ──────────────────────────────────────────────────────────

const DOMAINS = [
  { name: "RAG & Retrieval",  icon: "🔍", capability: "rag-evaluation",  color: "#6c63ff", count: 687  },
  { name: "Code Generation",  icon: "💻", capability: "code-generation", color: "#3ecfcf", count: 523  },
  { name: "Security Audit",   icon: "🔒", capability: "security-audit",  color: "#f87171", count: 298  },
  { name: "DeFi Analytics",   icon: "📊", capability: "defi-analytics",  color: "#f59e0b", count: 441  },
  { name: "Smart Contract",   icon: "📜", capability: "smart-contract",  color: "#a78bfa", count: 376  },
  { name: "Data Analysis",    icon: "🧮", capability: "data-analysis",   color: "#34d399", count: 389  },
  { name: "Summarization",    icon: "📝", capability: "summarization",   color: "#60a5fa", count: 312  },
  { name: "Compliance",       icon: "⚖️", capability: "compliance",      color: "#fb923c", count: 187  },
  { name: "Content Writing",  icon: "✍️", capability: "content-writing", color: "#f472b6", count: 264  },
  { name: "Translation",      icon: "🌐", capability: "translation",     color: "#4ade80", count: 143  },
];

// ── Transaction types with kid-friendly language ─────────────────────────────

const TX_TYPES = [
  {
    id: "batch",
    icon: "⚡",
    label: "Batch HIP-551",
    tagline: "Do EVERYTHING at once!",
    explain: "The payment and proof happen in the same heartbeat. Like buying candy AND getting the receipt at the exact same second — super safe, can't be undone!",
    color: "#6c63ff",
    bg: "rgba(108,99,255,0.12)",
  },
  {
    id: "scheduled",
    icon: "⏰",
    label: "Scheduled",
    tagline: "Lock it in now, run it later!",
    explain: "Like pre-ordering a pizza. The deal is sealed on the blockchain RIGHT NOW, but the actual payment happens later. Nobody can cancel it!",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.12)",
  },
  {
    id: "atomic_swap",
    icon: "↔",
    label: "Atomic Swap",
    tagline: "Even trade, same moment!",
    explain: "You pay EXACTLY when they deliver. It's like a handshake where both hands move at the exact same millisecond. Nobody can cheat!",
    color: "#3ecfcf",
    bg: "rgba(62,207,207,0.12)",
  },
  {
    id: "standard",
    icon: "●",
    label: "Standard",
    tagline: "Simple and easy!",
    explain: "Just a regular payment. Quick, straightforward, and gets the job done. No surprises!",
    color: "#94a3b8",
    bg: "rgba(148,163,184,0.10)",
  },
];

// ── Keyword → capability extraction ─────────────────────────────────────────

const KEYWORD_MAP: [RegExp, string][] = [
  [/rag|retriev|pipeline|benchmark|embed|vector|chunk|qa system/i, "rag-evaluation"],
  [/summar|brief|tldr|condense|digest|shorten/i, "summarization"],
  [/code|program|develop|debug|function|script|python|javascript|typescript|solidity|build.*app/i, "code-generation"],
  [/securi|audit|vulnerab|hack|pentest|exploit|safe.*contract|check.*contract/i, "security-audit"],
  [/defi|yield|liquidity|swap.*price|market.*price|crypto.*price|portfolio.*crypto|on.chain.*data/i, "defi-analytics"],
  [/comply|compliance|kyc|aml|legal|regulat|fraud|identity.*verif|sanction/i, "compliance"],
  [/content|write.*blog|blog|article|copy|marketing|seo|tweet|post/i, "content-writing"],
  [/smart.*contract|deploy.*contract|erc.20|erc.721|nft.*contract|dao|token.*contract/i, "smart-contract"],
  [/data|analyz|analytic|report|chart|dashboard|insight|metrics/i, "data-analysis"],
  [/translat|language|multilingual|local|convert.*language/i, "translation"],
];

function extractCapability(text: string): string {
  for (const [re, cap] of KEYWORD_MAP) {
    if (re.test(text)) return cap;
  }
  return "";
}

function capabilityToDomain(cap: string): string {
  return DOMAINS.find((d) => d.capability === cap)?.name ?? "RAG & Retrieval";
}

// ── Message types ────────────────────────────────────────────────────────────

type WidgetType = "domain-picker" | "tx-picker" | "hire-running" | "hire-done";

type ChatMessage = {
  id: string;
  from: "bot" | "user";
  text: string;
  widget?: WidgetType;
  timestamp: number;
};

type Stage =
  | "awaiting-goal"
  | "domain-pick"
  | "tx-pick"
  | "hiring"
  | "done"
  | "blocked";

// ── Props ─────────────────────────────────────────────────────────────────────

interface ChatbotHireProps {
  onHireStateChange: (state: HireState) => void;
  onStepsChange: (steps: HireStep[]) => void;
  onAgentSelected: (agentId: string | undefined) => void;
  onEligibleAgents: (ids: string[] | undefined) => void;
  onTxTypeChange: (txType: string) => void;
  onRunningChange: (running: boolean) => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChatbotHire({
  onHireStateChange,
  onStepsChange,
  onAgentSelected,
  onEligibleAgents,
  onTxTypeChange,
  onRunningChange,
}: ChatbotHireProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [stage, setStage] = useState<Stage>("awaiting-goal");
  const [selectedDomain, setSelectedDomain] = useState<typeof DOMAINS[0] | null>(null);
  const [selectedTx, setSelectedTx] = useState<typeof TX_TYPES[0] | null>(null);
  const [detectedCap, setDetectedCap] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [hireSteps, setHireSteps] = useState<HireStep[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const addMsg = useCallback((msg: Omit<ChatMessage, "id" | "timestamp">) => {
    setMessages((prev) => [
      ...prev,
      { ...msg, id: Math.random().toString(36).slice(2), timestamp: Date.now() },
    ]);
  }, []);

  const botSay = useCallback(
    (text: string, widget?: WidgetType, delay = 0) => {
      setIsTyping(true);
      setTimeout(() => {
        setIsTyping(false);
        addMsg({ from: "bot", text, widget });
      }, delay + 600);
    },
    [addMsg]
  );

  // Greeting on mount
  useEffect(() => {
    setTimeout(() => {
      setIsTyping(true);
      setTimeout(() => {
        setIsTyping(false);
        addMsg({
          from: "bot",
          text: "Hey there! 👋 I'm AgentRanker. Tell me what you need an AI agent to help with today — just describe it in your own words!",
        });
      }, 800);
    }, 300);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || stage !== "awaiting-goal") return;
    setInput("");
    addMsg({ from: "user", text });

    const cap = extractCapability(text);
    setDetectedCap(cap);

    const domainName = cap ? capabilityToDomain(cap) : "";
    const domainHint = domainName
      ? ` Looks like you might want something in the **${domainName}** space — but pick what fits best!`
      : "";

    botSay(
      `Nice! I'm searching through 34,422 on-chain agents for you.${domainHint} Click the domain that best describes what you need:`,
      "domain-picker",
      200
    );
    setStage("domain-pick");
  };

  const handleDomainSelect = (domain: typeof DOMAINS[0]) => {
    if (stage !== "domain-pick") return;
    setSelectedDomain(domain);
    addMsg({ from: "user", text: `${domain.icon} ${domain.name}` });

    botSay(
      `${domain.name} — great pick! 🎯 AgentRanker has **${domain.count.toLocaleString()} agents** registered in that space.\n\nNow, how should the payment work? Pick the style that sounds right to you:`,
      "tx-picker",
      200
    );
    setStage("tx-pick");
  };

  const handleTxSelect = async (tx: typeof TX_TYPES[0]) => {
    if (stage !== "tx-pick" || !selectedDomain) return;
    setSelectedTx(tx);
    setStage("hiring");
    onTxTypeChange(tx.id);
    addMsg({ from: "user", text: `${tx.icon} ${tx.label}` });

    botSay(
      `${tx.icon} ${tx.tagline} Let me find the highest-trust agent for **${selectedDomain.name}** and execute the payment on Hedera testnet...`,
      undefined,
      200
    );

    const cap = selectedDomain.capability;
    onHireStateChange("discovering");
    onRunningChange(true);
    setHireSteps([]);

    try {
      const result = await runAutonomousHire({
        goal: `I need help with ${selectedDomain.name.toLowerCase()}`,
        capability: cap,
        trust_threshold: 0.5,
        transaction_type: tx.id,
      });

      const steps = result.steps || [];
      const liveSteps: HireStep[] = [];

      const STEP_TO_HIRE_STATE: Record<string, HireState> = {
        discover: "discovering",
        filter: "filtering",
        select: "selecting",
        decide: "deciding",
        pay: "paying",
        serve: "serving",
      };

      for (let i = 0; i < steps.length; i++) {
        const step = steps[i];
        liveSteps.push(step);
        setHireSteps([...liveSteps]);
        onStepsChange([...liveSteps]);
        onHireStateChange(STEP_TO_HIRE_STATE[step.step_type] || "discovering");

        if (step.step_type === "select" && step.data?.agent_id) {
          onAgentSelected(step.data.agent_id as string);
        }
        if (step.step_type === "filter") {
          onEligibleAgents(undefined);
        }
        await new Promise((r) => setTimeout(r, 250 + Math.min((step.elapsed_ms || 0), 500)));
      }

      onRunningChange(false);

      if (result.success) {
        onHireStateChange("complete");
        const agentName = result.selected_agent_name ?? "the agent";
        const payStep = steps.find((s) => s.step_type === "pay");
        const txId = payStep?.data?.tx_id as string | undefined;
        const hcsId = payStep?.data?.hcs_message_id as string | undefined;

        botSay(
          `🎉 Done! AgentRanker hired **${agentName}** for you!\n\n` +
          `Real transaction on Hedera testnet:\n• Tx: \`${txId ?? "n/a"}\`\n• HCS audit: \`${hcsId ?? "n/a"}\`\n\nClick the HashScan links in the trace below to verify on-chain! ✅`,
          undefined,
          400
        );
        setStage("done");
      } else {
        onHireStateChange("blocked");
        botSay(
          `😔 The hire was blocked. ${result.error ?? "No agents passed the trust gate."} Try lowering the trust threshold or picking a different domain!`,
          undefined,
          400
        );
        setStage("blocked");
      }
    } catch (err) {
      onRunningChange(false);
      onHireStateChange("blocked");
      botSay(
        `⚠️ Something went wrong: ${err instanceof Error ? err.message : String(err)}. Make sure the backend is running on port 8000.`,
        undefined,
        400
      );
      setStage("blocked");
    }
  };

  const handleReset = () => {
    setMessages([]);
    setInput("");
    setStage("awaiting-goal");
    setSelectedDomain(null);
    setSelectedTx(null);
    setDetectedCap("");
    setHireSteps([]);
    onHireStateChange("idle");
    onStepsChange([]);
    onAgentSelected(undefined);
    onEligibleAgents(undefined);
    onRunningChange(false);
    setTimeout(() => {
      setIsTyping(true);
      setTimeout(() => {
        setIsTyping(false);
        addMsg({
          from: "bot",
          text: "Hey again! 👋 What do you need an AI agent to help with this time?",
        });
      }, 700);
    }, 200);
  };

  return (
    <div
      className="flex flex-col rounded-2xl overflow-hidden"
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(255,255,255,0.08)",
        height: "520px",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3 flex-shrink-0"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-base"
            style={{ background: "rgba(108,99,255,0.15)", border: "1px solid rgba(108,99,255,0.3)" }}
          >
            ⬡
          </div>
          <div>
            <div className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
              AgentRanker Chat
            </div>
            <div className="text-xs" style={{ color: "#64748b" }}>
              Find + hire the best agent for you
            </div>
          </div>
        </div>
        {(stage === "done" || stage === "blocked") && (
          <button
            onClick={handleReset}
            className="text-xs px-3 py-1.5 rounded-lg transition-all"
            style={{
              background: "rgba(108,99,255,0.1)",
              border: "1px solid rgba(108,99,255,0.25)",
              color: "#a5b4fc",
            }}
          >
            Start over
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scrollbar-thin">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`flex ${msg.from === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[88%] ${msg.from === "user" ? "order-2" : ""}`}
              >
                {/* Text bubble */}
                <div
                  className="px-4 py-2.5 rounded-2xl text-sm leading-relaxed"
                  style={
                    msg.from === "user"
                      ? {
                          background: "linear-gradient(135deg, #6c63ff, #3ecfcf)",
                          color: "#fff",
                          borderBottomRightRadius: "4px",
                        }
                      : {
                          background: "rgba(255,255,255,0.05)",
                          border: "1px solid rgba(255,255,255,0.08)",
                          color: "#cbd5e1",
                          borderBottomLeftRadius: "4px",
                        }
                  }
                >
                  {msg.text.split("\n").map((line, i) => {
                    // Bold **text**
                    const parts = line.split(/\*\*(.*?)\*\*/g);
                    return (
                      <p key={i} className={i > 0 ? "mt-1" : ""}>
                        {parts.map((p, j) =>
                          j % 2 === 1 ? (
                            <strong key={j} style={{ color: msg.from === "user" ? "#fff" : "#e2e8f0" }}>
                              {p}
                            </strong>
                          ) : (
                            <span key={j}>{p}</span>
                          )
                        )}
                      </p>
                    );
                  })}
                </div>

                {/* Domain picker widget */}
                {msg.widget === "domain-picker" && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                    className="mt-3 grid grid-cols-2 gap-2"
                  >
                    {DOMAINS.map((domain) => {
                      const isSelected = selectedDomain?.capability === domain.capability;
                      const isDisabled = stage !== "domain-pick";
                      return (
                        <motion.button
                          key={domain.capability}
                          onClick={() => !isDisabled && handleDomainSelect(domain)}
                          whileHover={!isDisabled ? { scale: 1.03 } : {}}
                          whileTap={!isDisabled ? { scale: 0.97 } : {}}
                          className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left transition-all duration-200"
                          style={{
                            background: isSelected
                              ? `${domain.color}20`
                              : "rgba(255,255,255,0.04)",
                            border: `1px solid ${isSelected ? domain.color : "rgba(255,255,255,0.09)"}`,
                            cursor: isDisabled ? "default" : "pointer",
                            boxShadow: isSelected ? `0 0 16px ${domain.color}40` : "none",
                          }}
                        >
                          <span className="text-xl flex-shrink-0">{domain.icon}</span>
                          <div className="min-w-0">
                            <div
                              className="text-xs font-semibold truncate"
                              style={{ color: isSelected ? domain.color : "#cbd5e1" }}
                            >
                              {domain.name}
                            </div>
                            <div className="text-xs" style={{ color: "#475569" }}>
                              {domain.count.toLocaleString()} agents
                            </div>
                          </div>
                          {isSelected && (
                            <span className="ml-auto text-xs" style={{ color: domain.color }}>✓</span>
                          )}
                        </motion.button>
                      );
                    })}
                  </motion.div>
                )}

                {/* TX type picker widget */}
                {msg.widget === "tx-picker" && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                    className="mt-3 space-y-2"
                  >
                    {TX_TYPES.map((tx) => {
                      const isSelected = selectedTx?.id === tx.id;
                      const isDisabled = stage !== "tx-pick";
                      return (
                        <motion.button
                          key={tx.id}
                          onClick={() => !isDisabled && handleTxSelect(tx)}
                          whileHover={!isDisabled ? { scale: 1.01, x: 2 } : {}}
                          whileTap={!isDisabled ? { scale: 0.99 } : {}}
                          className="w-full flex items-start gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200"
                          style={{
                            background: isSelected ? tx.bg : "rgba(255,255,255,0.03)",
                            border: `1px solid ${isSelected ? tx.color : "rgba(255,255,255,0.08)"}`,
                            cursor: isDisabled ? "default" : "pointer",
                            boxShadow: isSelected ? `0 0 20px ${tx.color}30` : "none",
                          }}
                        >
                          <span className="text-2xl flex-shrink-0 mt-0.5">{tx.icon}</span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span
                                className="text-sm font-bold"
                                style={{ color: isSelected ? tx.color : "#e2e8f0" }}
                              >
                                {tx.label}
                              </span>
                              <span
                                className="text-xs font-medium px-2 py-0.5 rounded-full"
                                style={{
                                  background: `${tx.color}15`,
                                  color: tx.color,
                                }}
                              >
                                {tx.tagline}
                              </span>
                            </div>
                            <p className="text-xs mt-1 leading-relaxed" style={{ color: "#94a3b8" }}>
                              {tx.explain}
                            </p>
                          </div>
                        </motion.button>
                      );
                    })}
                  </motion.div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Typing indicator */}
        {isTyping && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex justify-start"
          >
            <div
              className="flex items-center gap-1.5 px-4 py-3 rounded-2xl"
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-2 h-2 rounded-full"
                  style={{ background: "#6c63ff" }}
                  animate={{ y: [0, -5, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                />
              ))}
            </div>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        className="px-4 py-3 flex-shrink-0"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        {stage === "awaiting-goal" ? (
          <form
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="flex gap-2"
          >
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. I need my DeFi portfolio analyzed..."
              className="flex-1 px-4 py-2.5 rounded-xl text-sm outline-none"
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#e2e8f0",
              }}
              autoFocus
            />
            <button
              type="submit"
              disabled={!input.trim()}
              className="px-4 py-2.5 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: input.trim()
                  ? "linear-gradient(135deg, #6c63ff, #3ecfcf)"
                  : "rgba(255,255,255,0.06)",
                color: input.trim() ? "#fff" : "#475569",
                cursor: input.trim() ? "pointer" : "default",
              }}
            >
              Send
            </button>
          </form>
        ) : stage === "hiring" ? (
          <div
            className="flex items-center gap-3 px-4 py-2.5 rounded-xl"
            style={{ background: "rgba(108,99,255,0.08)", border: "1px solid rgba(108,99,255,0.2)" }}
          >
            <motion.div
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ background: "#6c63ff" }}
              animate={{ scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }}
              transition={{ duration: 1.2, repeat: Infinity }}
            />
            <span className="text-sm" style={{ color: "#a5b4fc" }}>
              AgentRanker is hiring on Hedera testnet...
            </span>
          </div>
        ) : stage === "domain-pick" || stage === "tx-pick" ? (
          <div
            className="px-4 py-2.5 rounded-xl text-sm text-center"
            style={{ background: "rgba(255,255,255,0.03)", color: "#64748b" }}
          >
            {stage === "domain-pick" ? "👆 Pick a domain above to continue" : "👆 Choose your payment style above"}
          </div>
        ) : (
          <div
            className="px-4 py-2.5 rounded-xl text-sm text-center"
            style={{ background: "rgba(74,222,128,0.06)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.15)" }}
          >
            ✓ {stage === "done" ? "Hire complete — check the trace below!" : "Blocked — click Start over to try again"}
          </div>
        )}
      </div>
    </div>
  );
}
