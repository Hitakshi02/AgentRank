"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface NavProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export default function Nav({ activeTab, onTabChange }: NavProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const tabs = [
    { id: "hero", label: "Overview" },
    { id: "rankings", label: "Rankings" },
    { id: "demo", label: "Live Demo" },
  ];

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50"
      style={{
        backdropFilter: "blur(12px)",
        background: "rgba(5, 5, 16, 0.8)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center gap-2 cursor-pointer"
          onClick={() => onTabChange("hero")}
        >
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <polygon
              points="14,2 26,8 26,20 14,26 2,20 2,8"
              fill="none"
              stroke="url(#hexGrad)"
              strokeWidth="1.5"
            />
            <polygon
              points="14,7 21,10.5 21,17.5 14,21 7,17.5 7,10.5"
              fill="url(#hexGradFill)"
              opacity="0.6"
            />
            <defs>
              <linearGradient id="hexGrad" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#6c63ff" />
                <stop offset="100%" stopColor="#3ecfcf" />
              </linearGradient>
              <linearGradient id="hexGradFill" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#6c63ff" stopOpacity="0.5" />
                <stop offset="100%" stopColor="#3ecfcf" stopOpacity="0.3" />
              </linearGradient>
            </defs>
          </svg>
          <span
            className="text-lg font-bold"
            style={{
              background: "linear-gradient(135deg, #6c63ff, #3ecfcf)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            AgentRanker
          </span>
        </motion.div>

        {/* Nav Links */}
        <div className="hidden md:flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              onMouseEnter={() => setHovered(tab.id)}
              onMouseLeave={() => setHovered(null)}
              className="relative px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
              style={{
                color: activeTab === tab.id ? "#e2e8f0" : "#94a3b8",
              }}
            >
              {(activeTab === tab.id || hovered === tab.id) && (
                <motion.div
                  layoutId="nav-highlight"
                  className="absolute inset-0 rounded-lg"
                  style={{
                    background: "rgba(108, 99, 255, 0.15)",
                    border: "1px solid rgba(108, 99, 255, 0.3)",
                  }}
                  transition={{ type: "spring", bounce: 0.2, duration: 0.3 }}
                />
              )}
              <span className="relative z-10">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Right side badges */}
        <div className="flex items-center gap-3">
          <div
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium"
            style={{
              background: "rgba(62, 207, 207, 0.1)",
              border: "1px solid rgba(62, 207, 207, 0.3)",
              color: "#3ecfcf",
            }}
          >
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: "#3ecfcf", boxShadow: "0 0 6px #3ecfcf" }}
            />
            Hedera Testnet
          </div>
          <div
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium"
            style={{
              background: "rgba(108, 99, 255, 0.1)",
              border: "1px solid rgba(108, 99, 255, 0.3)",
              color: "#a5b4fc",
            }}
          >
            34,422 agents
          </div>
        </div>
      </div>
    </nav>
  );
}
