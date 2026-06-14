"""
RequesterAgent — autonomous agent-to-agent hiring loop.

Operates with zero human involvement:
  1. DISCOVER  — pulls ranked leaderboard from BigQuery + RAGAS
  2. FILTER    — narrows to the requested capability above the trust threshold
  3. SELECT    — picks the highest-trust serviceable agent (is_serviceable=True
                 preferred); falls back to any eligible agent with a trace note
  4. DECIDE    — rule-based reasoning explaining the choice
                 (optional LLM-narrated mode via narrate_with_llm=True)
  5. PAY       — trust-gated HBAR payment on Hedera; decision always logged to HCS
  6. SERVE     — real x402 pay-per-request call; RAGAS live or labelled mock

Returns an AutonomousHireResult with a step-by-step trace so the frontend
can animate each decision. Mock path always works with no credentials.
"""

import time
from dataclasses import asdict

from core.leaderboard import build_leaderboard
from core.models import Agent, AutonomousHireResult, HireStep, PaymentDecision
from core.services import run_service


def _rule_based_reasoning(
    goal: str,
    candidate: Agent,
    all_candidates: list,
    threshold: float,
    serviceable_only: bool,
) -> str:
    rank = next(
        (i + 1 for i, a in enumerate(all_candidates) if a.agent_id == candidate.agent_id),
        "?",
    )
    parts = [
        f'Goal: "{goal}".',
        f"Selected: {candidate.name} (rank #{rank} of {len(all_candidates)} eligible candidates).",
        f"Trust score: {candidate.trust_score:.3f} (threshold: {threshold:.2f}).",
    ]
    if serviceable_only:
        parts.append("Agent has a verified service endpoint (is_serviceable=True).")
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
        "the capability, threshold, and serviceability requirements."
    )
    return "  ".join(parts)


class RequesterAgent:
    """
    Autonomous agent that discovers, evaluates, selects, and pays for
    another agent's service — entirely without human input.

    Args:
        goal:              Natural-language task description.
        capability:        ERC-8004 capability tag to filter on.
        trust_threshold:   Minimum trust score (0–1) to consider an agent.
        narrate_with_llm:  Use Claude API for decision narrative (zero cost by default).
        requester_id:      Identifier for this requester (logged to HCS).
        amount_usd:        HBAR payment amount for the brokerage settlement.
    """

    def __init__(
        self,
        goal: str = "I need a RAG pipeline evaluated",
        capability: str = "rag-evaluation",
        trust_threshold: float = 0.5,
        narrate_with_llm: bool = False,
        requester_id: str = "requester-agent-v1",
        amount_usd: float = 0.01,
        transaction_type: str = "batch",
    ):
        self.goal = goal
        self.capability = capability
        self.trust_threshold = trust_threshold
        self.narrate_with_llm = narrate_with_llm
        self.requester_id = requester_id
        self.amount_usd = amount_usd
        self.transaction_type = transaction_type

    # ------------------------------------------------------------------
    def hire(self, bq_client, ragas_client, hedera_client, x402_client=None) -> AutonomousHireResult:
        result  = AutonomousHireResult(goal=self.goal, capability=self.capability)
        t_start = time.monotonic()

        # ── Step 1: DISCOVER ──────────────────────────────────────────
        t0 = time.monotonic()
        try:
            all_agents = bq_client.get_erc8004_agents()
            ranked     = build_leaderboard(all_agents, ragas_client)
        except Exception as exc:
            result.steps.append(HireStep(
                step_type="discover", title="Discover agents", status="error",
                description=f"Failed to load leaderboard: {exc}",
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            ))
            result.error = str(exc)
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        result.steps.append(HireStep(
            step_type="discover", title="Discover agents", status="ok",
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
        if not eligible:
            reason = (
                f"no agents with capability '{self.capability}'"
                if not any(a.capability == self.capability for a in ranked)
                else f"no agents above trust threshold {self.trust_threshold:.2f}"
            )
            result.steps.append(HireStep(
                step_type="filter", title="Filter by capability + trust", status="blocked",
                description=f"No eligible agents found. Reason: {reason}.",
                data={"threshold": self.trust_threshold, "capability": self.capability},
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            ))
            result.error = "No eligible agents meet the capability and trust threshold."
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        result.steps.append(HireStep(
            step_type="filter", title="Filter by capability + trust", status="ok",
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
        serviceable = [a for a in eligible if a.is_serviceable]
        if serviceable:
            selected         = serviceable[0]
            serviceable_only = True
            select_note      = (
                f"Chose highest-trust serviceable agent "
                f"({len(serviceable)} of {len(eligible)} eligible have a live endpoint)."
            )
        else:
            selected         = eligible[0]
            serviceable_only = False
            select_note      = (
                "No curated serviceable agents in eligible set — "
                "selected highest-trust agent. Service result will be labelled 'unavailable'."
            )

        result.selected_agent_id   = selected.agent_id
        result.selected_agent_name = selected.name

        result.steps.append(HireStep(
            step_type="select", title="Select best agent", status="ok",
            description=(
                f"{select_note}  Selected: {selected.name} "
                f"(trust_score={selected.trust_score:.3f}). "
                f"Agent ID: {selected.agent_id}. "
                f"On-chain reputation: {selected.erc8004_reputation}/100. "
                f"Serviceable: {selected.is_serviceable}."
            ),
            data={
                "agent_id":           selected.agent_id,
                "agent_name":         selected.name,
                "trust_score":        selected.trust_score,
                "erc8004_reputation": selected.erc8004_reputation,
                "hedera_topic_id":    selected.hedera_topic_id,
                "supports_x402":      selected.supports_x402,
                "is_serviceable":     selected.is_serviceable,
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        # ── Step 4: DECIDE ─────────────────────────────────────────────
        t0 = time.monotonic()
        reasoning = self._build_reasoning(selected, eligible, serviceable_only)
        result.steps.append(HireStep(
            step_type="decide", title="Autonomous decision", status="ok",
            description=reasoning,
            data={
                "mode":                  "llm" if self.narrate_with_llm else "rule-based",
                "candidates_considered": len(eligible),
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        # ── Step 5: PAY ────────────────────────────────────────────────
        t0 = time.monotonic()
        try:
            pay_kwargs = dict(
                requester_id=self.requester_id,
                target_agent_id=selected.agent_id,
                trust_score=selected.trust_score,
                threshold=self.trust_threshold,
                amount_usd=self.amount_usd,
            )
            if self.transaction_type == "batch":
                decision: PaymentDecision = hedera_client.batch_hire(
                    **pay_kwargs,
                    agent_topic_id=selected.hedera_topic_id,
                )
            elif self.transaction_type == "scheduled":
                decision: PaymentDecision = hedera_client.schedule_hire(**pay_kwargs)
            elif self.transaction_type == "atomic_swap":
                decision: PaymentDecision = hedera_client.atomic_swap_hire(**pay_kwargs)
            else:
                decision: PaymentDecision = hedera_client.submit_payment(**pay_kwargs)
            result.payment_decision = asdict(decision)
        except Exception as exc:
            result.steps.append(HireStep(
                step_type="pay", title="Hedera payment", status="error",
                description=f"Payment call failed: {exc}",
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            ))
            result.error = str(exc)
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        tx_type_label = {
            "batch": "HIP-551 Batch",
            "scheduled": "Scheduled",
            "atomic_swap": "Atomic Swap",
        }.get(decision.transaction_type, "Standard")

        if decision.approved:
            pay_desc = (
                f"Payment APPROVED via Hedera [{tx_type_label}]. "
                f"${decision.amount_usd:.4f} HBAR transferred to {selected.name}. "
                f"Tx: {decision.tx_id}. "
                f"HCS audit entry: {decision.hcs_message_id}."
            )
            if decision.transaction_type == "scheduled" and decision.scheduled_at:
                pay_desc += f"  Scheduled for: {decision.scheduled_at}."
            if decision.batch_id:
                pay_desc += f"  Batch/Schedule ID: {decision.batch_id}."
            pay_status = "ok"
        else:
            pay_desc = (
                f"Payment BLOCKED [{tx_type_label}]. Trust score {decision.trust_score:.3f} "
                f"< threshold {decision.threshold:.2f}. "
                f"Decision logged to HCS: {decision.hcs_message_id}."
            )
            pay_status = "blocked"

        result.steps.append(HireStep(
            step_type="pay", title=f"Hedera payment [{tx_type_label}]", status=pay_status,
            description=pay_desc,
            data={
                "approved":          decision.approved,
                "tx_id":             decision.tx_id,
                "hcs_message_id":    decision.hcs_message_id,
                "amount_usd":        decision.amount_usd,
                "reason":            decision.reason,
                "transaction_type":  decision.transaction_type,
                "batch_id":          decision.batch_id,
                "scheduled_at":      decision.scheduled_at,
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        if not decision.approved:
            result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return result

        # ── Step 6: SERVE ──────────────────────────────────────────────
        t0 = time.monotonic()
        serve_error = None

        if x402_client is not None:
            try:
                service_response = run_service(
                    capability=self.capability,
                    agent_id=selected.agent_id,
                    x402_client=x402_client,
                    ragas_client=ragas_client,
                    requester_id=self.requester_id,
                )
            except Exception as exc:
                serve_error      = str(exc)
                service_response = {
                    "task":    self.capability,
                    "summary": f"Service call failed: {exc}",
                    "source":  "error",
                }
        else:
            service_response = {
                "task":    self.capability,
                "summary": "x402 client not available — service not executed.",
                "source":  "unavailable",
            }

        result.service_output = {
            **service_response,
            "served_by":    selected.name,
            "served_by_id": selected.agent_id,
            "tx_id":        decision.tx_id,
        }

        x402_payment = service_response.get("x402_payment", {})
        result.steps.append(HireStep(
            step_type="serve",
            title="Service delivered via x402",
            status="error" if serve_error else "ok",
            description=(
                f"{selected.name} completed the task via x402 pay-per-request. "
                f"x402 tx: {x402_payment.get('tx_id', 'n/a')}. "
                f"Source: {service_response.get('source', 'unknown')}. "
                f"{service_response.get('summary', '')}"
            ),
            data=result.service_output,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        ))

        if not serve_error:
            result.success = True

        result.total_elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return result

    # ------------------------------------------------------------------
    def _build_reasoning(self, selected: Agent, eligible: list, serviceable_only: bool) -> str:
        if self.narrate_with_llm:
            return self._llm_reasoning(selected, eligible)
        return _rule_based_reasoning(
            self.goal, selected, eligible, self.trust_threshold, serviceable_only
        )

    def _llm_reasoning(self, selected: Agent, eligible: list) -> str:
        try:
            import anthropic
            client = anthropic.Anthropic()
            candidates_summary = "\n".join(
                f"- {a.name}: trust={a.trust_score:.3f}, "
                f"reputation={a.erc8004_reputation}/100, "
                f"ragas_avg={a.ragas.average if a.ragas else 'N/A'}, "
                f"serviceable={a.is_serviceable}"
                for a in eligible[:5]
            )
            prompt = (
                f"You are an autonomous AI agent deciding which agent to hire.\n"
                f"Goal: {self.goal}\n"
                f"Eligible agents (sorted by trust score):\n{candidates_summary}\n\n"
                f"You chose: {selected.name} (trust={selected.trust_score:.3f}, "
                f"serviceable={selected.is_serviceable}).\n"
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
                self.goal, selected, eligible, self.trust_threshold, False
            )
