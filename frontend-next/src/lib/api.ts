const API = "http://localhost:8000/api";

export interface RagasScores {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  average?: number;
}

export interface Agent {
  agent_id: string;
  name: string;
  description: string;
  capability: string;
  trust_score: number;
  erc8004_reputation: number | null;
  erc8004_address: string | null;
  supports_x402: boolean;
  is_serviceable: boolean;
  hedera_topic_id: string | null;
  domain: string | null;
  ragas_average: number | null;
  ragas: RagasScores | null;
}

export interface HireStep {
  step_type: string;
  title: string;
  status: "ok" | "blocked" | "error";
  description: string;
  data: Record<string, unknown>;
  elapsed_ms: number;
}

export interface PaymentDecision {
  requester_id: string;
  target_agent_id: string;
  trust_score: number;
  threshold: number;
  approved: boolean;
  amount_usd: number;
  tx_id: string | null;
  hcs_message_id: string | null;
  reason: string;
  transaction_type: string;
  batch_id: string | null;
  scheduled_at: string | null;
}

export interface HireResult {
  success: boolean;
  selected_agent_id: string | null;
  selected_agent_name: string | null;
  steps: HireStep[];
  payment_decision: PaymentDecision | null;
  service_output: Record<string, unknown> | null;
  total_elapsed_ms: number;
  error: string | null;
  source: Record<string, string>;
  goal: string;
  capability: string;
}

export interface EcosystemStats {
  total_agents: number;
  agents_with_x402: number;
  avg_reputation: number;
  registrations_last_30d: number;
  reputation_distribution: Record<string, number>;
}

export interface RankingAgent {
  agent_id: string;
  name: string;
  naive_score: number;
  sybil_resistant_score: number;
  naive_rank: number;
  sybil_rank: number;
  rank_delta: number;
  flagged_as_sybil: boolean;
}

export interface RankingComparison {
  agents: RankingAgent[];
  sybil_agents_detected: number;
  total_agents: number;
}

export async function fetchLeaderboard(
  x402Only?: boolean
): Promise<{ agents: Agent[]; source: Record<string, string> }> {
  const params = new URLSearchParams();
  if (x402Only) params.set("x402_only", "true");
  const res = await fetch(`${API}/leaderboard?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Leaderboard fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchAnalytics(): Promise<{
  stats: EcosystemStats;
  source: Record<string, string>;
}> {
  const res = await fetch(`${API}/analytics`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Analytics fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchRankingComparison(): Promise<{
  comparison: RankingComparison | null;
  source: Record<string, string>;
}> {
  const res = await fetch(`${API}/ranking/comparison`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Ranking comparison fetch failed: ${res.status}`);
  const raw = await res.json();
  const cmp = raw.comparison;
  if (!cmp) return { comparison: null, source: raw.source || {} };

  // API returns `deltas[]` with `sybil_score` and `flags[]`; map to our frontend shape
  const agents: RankingAgent[] = (cmp.deltas || []).map((d: {
    agent_id: string;
    naive_rank: number;
    sybil_rank: number;
    rank_delta: number;
    naive_score: number;
    sybil_score: number;
    flags: string[];
  }) => ({
    agent_id: d.agent_id,
    name: d.agent_id,
    naive_score: d.naive_score,
    sybil_resistant_score: d.sybil_score,
    naive_rank: d.naive_rank,
    sybil_rank: d.sybil_rank,
    rank_delta: d.rank_delta,
    flagged_as_sybil: (d.flags || []).length > 0,
  }));

  agents.sort((a, b) => a.sybil_rank - b.sybil_rank);

  return {
    comparison: {
      agents,
      sybil_agents_detected: agents.filter((a) => a.flagged_as_sybil).length,
      total_agents: agents.length,
    },
    source: raw.source || {},
  };
}

export async function runAutonomousHire(params: {
  goal: string;
  capability: string;
  trust_threshold: number;
  transaction_type: string;
}): Promise<HireResult> {
  const res = await fetch(`${API}/autonomous-hire`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Hire failed: ${res.status}`);
  return res.json();
}

export async function runX402Service(resource_id: string): Promise<unknown> {
  const res = await fetch(`${API}/x402/service`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resource_id }),
  });
  if (!res.ok) throw new Error(`x402 service failed: ${res.status}`);
  return res.json();
}

export async function fetchAuditLog(agent_id: string): Promise<unknown> {
  const res = await fetch(`${API}/identity/${agent_id}/audit`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Audit log fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchDomains(): Promise<{ domains: Record<string, number>; source: Record<string, string> }> {
  const res = await fetch(`${API}/domains`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Domains fetch failed: ${res.status}`);
  return res.json();
}
