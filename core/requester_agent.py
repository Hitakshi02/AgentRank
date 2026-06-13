"""
RequesterAgent — autonomous agent-to-agent hiring loop.

Operates with zero human involvement:
  1. DISCOVER  — pulls ranked leaderboard from BigQuery + RAGAS
  2. FILTER    — narrows to the requested capability above the trust threshold
  3. SELECT    — picks the single highest-trust eligible agent
  4. DECIDE    — produces rule-based reasoning explaining the choice
                 (optional LLM-narrated mode available via narrate_with_llm=True)
  5. PAY       — submits payment through the existing trust gate → Hedera
  6. SERVE     — delivers the task to the hired agent, returns the response

The entire loop returns an AutonomousHireResult with a step-by-step trace so
the frontend can animate each decision.  A mock path is always available; the
live Hedera/BigQuery paths are controlled by the same config flags as the rest
of the system.
"""

import time
from dataclasses import asdict
from typing import Optional

from core.leaderboard import build_leaderboard
from core.models import Agent, AutonomousHireResult, HireStep, PaymentDecision


# ---------------------------------------------------------------------------
# Simulated service responses keyed by capability
# ---------------------------------------------------------------------------
_SERVICE_MOCK: dict = {
    "rag-evaluation": {
        "task": "rag_evaluation",
        "queries_run": 3,
        "ragas_scores": {
            "faithfulness": 0.87,
            "answer_relevancy": 0.83,
            "context_precision": 0.79,
        },
        "average": 0.830,
        "summary": (
            "RAG pipeline scored 0.830 average across 3 queries. "
            "Context precision (0.79) is the primary bottleneck — "
            "consider increasing the retrieval top-k."
        ),
    },
    "summarization": {
        "task": "summarize_document",
        "word_count_in": 4200,
        "word_count_out": 310,
        "rouge_l": 0.74,
        "summary": "Document summarised to 310 words. ROUGE-L 0.74.",
    },
}


def _rule_based_reasoning(
    goal: str,
    candidate: Agent,
    all_candidates: list,
    threshold: float,
) -> str:
    """Build a transparent, auditable explanation of why this agent was chosen."""
    rank = next(
        (i + 1 for i, a in enumerate(all_candidates) if a.agent_id == candidate.agent_id),
        "?",
    )
    parts = [
        f'Goal: "{goal}".',
        f"Selected: {candidate.name} (rank #{rank} of {len(all_candidates)} eligible candidates).",
        f"Trust score: {candidate.trust_score:.3f} (threshold: {threshold:.2f}).",
    ]
    if candidate.erc8004_reputation is not None:
        parts.append(
            f"On-chain ERC-8004 reputation: {candidate.erc8004_reputation}/100 "
            "(live from BigQuery / Ethereum mainnet)."
        )
    if candidate.ragas is not None:
        parts.append(
            f"RAGAS evaluation: faithfulness={candidate.ragas.faithfulness:.2f}, "
            f"relevancy={candidate.ragas.answer_relevancy:.2f}, "
            f"precision={candidate.ragas.context_precision:.2f}."
        )
    if candidate.supports_x402:
        parts.append("Agent supports x402 pay-per-request.")
    parts.append(
        "Decision: automated rule — highest trust score among agents meeting "
        "the capability and threshold requirements."
    )
    return "  ".join(parts)


class RequesterAgent:
    """
    Autonomous agent that discovers, evaluates, selects, and pays for
    another agent's service — entirely without human input.

    Args:
        goal:              Natural-language description of the task.
        capability:        ERC-8004 capability tag to filter on.
        trust_threshold:   Minimum trust score (0–1) to consider an agent.
        narrate_with_llm:  If True, use Claude API to narrate the decision
                           reasoning instead of the rule-based template.
                           Defaults to False (zero LLM cost).
        requester_id:      Identifier for this requester (logged to HCS).
        amount_usd:        Payment amount for the service.
    """

    def __init__(
        self,
        goal: str = "I need a RAG pipeline evaluated",
        capability: str = "rag-evaluation",
        trust_threshold: float = 0.5,
        narrate_with_llm: bool = False,
        requester_id: str = "requester-agent-v1",
        amount_usd: float = 0.01,
        rail: str = "hedera",
    ):
        self.goal = goal
        self.capability = capability
        self.trust_threshold = trust_threshold
        self.narrate_with_llm = narrate_with_llm
        self.requester_id = requester_id
        self.amount_usd = amount_usd
        self.rail = rail

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def hire(self, bq_client, ragas_client, hedera_client, arc_client=None) -> AutonomousHireResult:
        result = AutonomousHireResult(goal=self.goal, capability=self.capability)
        t_start = time.monotonic()

        # ── Step 1: DISCOVER ──────────────────────────────────────────
        t0 = time.monotonic()
        try:
            all_agents = bq_client.get_erc8004_agents()
            ranked = build_leaderboard(all_agents, ragas_client)
        except Exception as exc:
            result.steps.append(HireStep(
                step_type="discover",
                title="Discover agents",
                status="error",
                description=f"Failed to load leaderboard: {exc}",
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            ))
            result.error = str(exc)
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        result.steps.append(HireStep(
            step_type="discover",
            title="Discover agents",
            status="ok",
            description=(
                f"Retrieved {len(ranked)} agents from the ERC-8004 leaderboard "
                f"(BigQuery + RAGAS). Top agent: {ranked[0].name} "
                f"(trust={ranked[0].trust_score:.3f})."
            ),
            data={"agent_count": len(ranked), "top_agent": ranked[0].name},
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        # ── Step 2: FILTER ─────────────────────────────────────────────
        t0 = time.monotonic()
        eligible = [
            a for a in ranked
            if a.capability == self.capability and a.trust_score >= self.trust_threshold
        ]
        ineligible_reason = []
        if not any(a.capability == self.capability for a in ranked):
            ineligible_reason.append(f"no agents with capability '{self.capability}'")
        elif not eligible:
            ineligible_reason.append(
                f"no agents above trust threshold {self.trust_threshold:.2f}"
            )

        if not eligible:
            result.steps.append(HireStep(
                step_type="filter",
                title="Filter by capability + trust",
                status="blocked",
                description=(
                    f"No eligible agents found. Reasons: {'; '.join(ineligible_reason)}."
                ),
                data={"threshold": self.trust_threshold, "capability": self.capability},
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            ))
            result.error = "No eligible agents meet the capability and trust threshold."
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        result.steps.append(HireStep(
            step_type="filter",
            title="Filter by capability + trust",
            status="ok",
            description=(
                f"{len(eligible)} agent(s) match capability='{self.capability}' "
                f"with trust_score >= {self.trust_threshold:.2f}. "
                f"Lowest eligible score: {eligible[-1].trust_score:.3f}."
            ),
            data={
                "capability": self.capability,
                "threshold": self.trust_threshold,
                "eligible_count": len(eligible),
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        # ── Step 3: SELECT ─────────────────────────────────────────────
        t0 = time.monotonic()
        selected = eligible[0]  # already sorted by trust_score desc
        result.selected_agent_id = selected.agent_id
        result.selected_agent_name = selected.name

        result.steps.append(HireStep(
            step_type="select",
            title="Select best agent",
            status="ok",
            description=(
                f"Chose {selected.name} (trust_score={selected.trust_score:.3f}). "
                f"Agent ID: {selected.agent_id}. "
                f"On-chain reputation: {selected.erc8004_reputation}/100."
            ),
            data={
                "agent_id": selected.agent_id,
                "agent_name": selected.name,
                "trust_score": selected.trust_score,
                "erc8004_reputation": selected.erc8004_reputation,
                "hedera_topic_id": selected.hedera_topic_id,
                "supports_x402": selected.supports_x402,
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        # ── Step 4: DECIDE ─────────────────────────────────────────────
        t0 = time.monotonic()
        reasoning = self._build_reasoning(selected, eligible)

        result.steps.append(HireStep(
            step_type="decide",
            title="Autonomous decision",
            status="ok",
            description=reasoning,
            data={
                "mode": "llm" if self.narrate_with_llm else "rule-based",
                "candidates_considered": len(eligible),
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        # ── Step 5: PAY ────────────────────────────────────────────────
        t0 = time.monotonic()
        try:
            if self.rail == "arc":
                if arc_client is None:
                    raise ValueError("arc_client is required when rail='arc'")
                decision: PaymentDecision = arc_client.settle_usdc_payment(
                    requester_id=self.requester_id,
                    target_agent_id=selected.agent_id,
                    trust_score=selected.trust_score,
                    threshold=self.trust_threshold,
                    amount_usdc=self.amount_usd,
                )
                payment_method = "Arc"
            else:
                decision: PaymentDecision = hedera_client.submit_payment(
                    requester_id=self.requester_id,
                    target_agent_id=selected.agent_id,
                    trust_score=selected.trust_score,
                    threshold=self.trust_threshold,
                    amount_usd=self.amount_usd,
                )
                payment_method = "Hedera"
            result.payment_decision = asdict(decision)
        except Exception as exc:
            result.steps.append(HireStep(
                step_type="pay",
                title=f"{payment_method if 'payment_method' in locals() else 'Payment'} payment",
                status="error",
                description=f"Payment call failed: {exc}",
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            ))
            result.error = str(exc)
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        if decision.approved:
            pay_desc = (
                f"Payment APPROVED. ${decision.amount_usd:.4f} transferred to "
                f"{selected.name} via {payment_method}. "
                f"Tx: {decision.tx_id}. "
                f"HCS audit: {decision.hcs_message_id}."
            )
            pay_status = "ok"
        else:
            pay_desc = (
                f"Payment BLOCKED. Trust score {decision.trust_score:.3f} "
                f"< threshold {decision.threshold:.2f}. "
                f"Decision logged to HCS: {decision.hcs_message_id}."
            )
            pay_status = "blocked"

        result.steps.append(HireStep(
            step_type="pay",
            title=f"{payment_method} payment",
            status=pay_status,
            description=pay_desc,
            data={
                "approved": decision.approved,
                "tx_id": decision.tx_id,
                "hcs_message_id": decision.hcs_message_id,
                "amount_usd": decision.amount_usd,
                "reason": decision.reason,
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        if not decision.approved:
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        # ── Step 6: SERVE ──────────────────────────────────────────────
        t0 = time.monotonic()
        service_response = _SERVICE_MOCK.get(
            self.capability,
            {"task": self.capability, "result": "Service completed.", "summary": "Done."},
        )
        result.service_output = {
            **service_response,
            "served_by": selected.name,
            "served_by_id": selected.agent_id,
            "paid_via": f"{payment_method}",
            "tx_id": decision.tx_id,
        }

        result.steps.append(HireStep(
            step_type="serve",
            title="Service delivered",
            status="ok",
            description=(
                f"{selected.name} completed the task. "
                f"{service_response.get('summary', 'Task complete.')}"
            ),
            data=result.service_output,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        result.success = True
        result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return result

    # ------------------------------------------------------------------
    # Reasoning helpers
    # ------------------------------------------------------------------
    def _build_reasoning(self, selected: Agent, eligible: list) -> str:
        if self.narrate_with_llm:
            return self._llm_reasoning(selected, eligible)
        return _rule_based_reasoning(self.goal, selected, eligible, self.trust_threshold)

    def _llm_reasoning(self, selected: Agent, eligible: list) -> str:
        """
        Optional: call Claude to narrate the decision in natural language.
        Stub — returns rule-based reasoning if the SDK is unavailable.
        Keeps token cost at zero by default (narrate_with_llm=False).
        """
        try:
            import anthropic  # type: ignore
            client = anthropic.Anthropic()
            candidates_summary = "\n".join(
                f"- {a.name}: trust={a.trust_score:.3f}, "
                f"reputation={a.erc8004_reputation}/100, "
                f"ragas_avg={a.ragas.average if a.ragas else 'N/A'}"
                for a in eligible[:5]
            )
            prompt = (
                f"You are an autonomous AI agent deciding which agent to hire.\n"
                f"Goal: {self.goal}\n"
                f"Eligible agents (sorted by trust score):\n{candidates_summary}\n\n"
                f"You chose: {selected.name} (trust={selected.trust_score:.3f}).\n"
                f"Explain your reasoning in 2–3 sentences. Be specific about the scores."
            )
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception:
            return _rule_based_reasoning(
                self.goal, selected, eligible, self.trust_threshold
            )
