"""
Shared service execution logic.

Used by:
  - core/requester_agent.py  (SERVE step in the autonomous hire loop)
  - api/main.py              (/api/x402/service endpoint)

This ensures both code paths produce results through identical logic,
clearly labelled by source (ragas_live | ragas_mock).
"""

from typing import Optional


# Map capability tag -> x402 resource_id and capability metadata.
# The resource_id is what x402_client expects.
_CAPABILITY_MAP: dict = {
    "rag-evaluation":  "rag-eval",
    "summarization":   "summarize",
    "code-generation": "code-gen",
    "security-audit":  "sec-audit",
    "defi-analytics":  "defi-data",
    "compliance":      "compliance",
    "content-writing": "content",
    "smart-contract":  "smart-contract",
    "data-analysis":   "data-analysis",
    "translation":     "translate",
}


def compute_service_result(
    capability: str,
    agent_id: str,
    ragas_client,
) -> dict:
    """
    Run the actual evaluation for a capability and return a result dict.

    Source labelling:
      "ragas_live"  — real RAGAS evaluation ran (USE_LIVE_RAGAS=true)
      "ragas_mock"  — RAGAS fixture scores from fixtures/agents.json
      "mock"        — no RAGAS data, structured placeholder for non-RAGAS capabilities

    This function is the single source of truth for what a service returns.
    Both the x402/service endpoint and the SERVE step call this.
    """
    if capability == "rag-evaluation":
        scores = ragas_client.evaluate(agent_id)
        if scores is not None:
            # Determine whether we got live or fixture scores
            from config import USE_LIVE_RAGAS
            source = "ragas_live" if USE_LIVE_RAGAS else "ragas_mock"
            return {
                "task":         "rag_evaluation",
                "queries_run":  3,
                "ragas_scores": {
                    "faithfulness":      scores.faithfulness,
                    "answer_relevancy":  scores.answer_relevancy,
                    "context_precision": scores.context_precision,
                },
                "average": scores.average,
                "summary": (
                    f"RAG pipeline scored {scores.average:.3f} average across 3 queries. "
                    f"Context precision ({scores.context_precision:.2f}) "
                    f"{'is' if scores.context_precision < scores.faithfulness else 'and faithfulness are'}"
                    f" the {'primary bottleneck — consider increasing the retrieval top-k.' if scores.context_precision < 0.85 else 'both strong.'}"
                ),
                "source": source,
            }
        # No RAGAS data for this agent — return a clearly-labelled placeholder
        return {
            "task":         "rag_evaluation",
            "queries_run":  0,
            "ragas_scores": None,
            "average":      None,
            "summary":      f"No RAGAS evaluation data available for agent {agent_id!r}.",
            "source":       "unavailable",
        }

    elif capability == "summarization":
        return {
            "task":           "summarize_document",
            "word_count_in":  4200,
            "word_count_out": 310,
            "rouge_l":        0.74,
            "summary":        "Document summarised to 310 words. ROUGE-L 0.74.",
            "source":         "mock",
        }

    else:
        return {
            "task":    capability,
            "result":  "Service completed.",
            "summary": f"Capability '{capability}' completed.",
            "source":  "mock",
        }


def run_service(
    capability: str,
    agent_id: str,
    x402_client,
    ragas_client,
    requester_id: str = "requester-agent-v1",
) -> dict:
    """
    Execute the full x402 pay-per-request flow for a service, then return
    the real service result.

    Steps performed internally:
      1. get_payment_requirements  (what the provider charges)
      2. submit_x402_payment       (requester pays the provider)
      3. verify_x402_payment       (provider confirms on-chain)
      4. compute_service_result    (provider runs the actual work)

    Raises RuntimeError if payment verification fails.

    Returns the service result dict, augmented with:
      x402_payment: { tx_id, amount_tinybars, verified }
      served_via:   "x402"
    """
    resource_id = _CAPABILITY_MAP.get(capability, capability)

    requirements  = x402_client.get_payment_requirements(resource_id)
    payment_proof = x402_client.submit_x402_payment(requirements, requester_id)
    verified, reason = x402_client.verify_x402_payment(payment_proof, requirements)

    if not verified:
        raise RuntimeError(f"x402 payment not verified: {reason}")

    result = compute_service_result(capability, agent_id, ragas_client)
    result["x402_payment"] = {
        "tx_id":           payment_proof["tx_id"],
        "amount_tinybars": payment_proof["amount_tinybars"],
        "verified":        verified,
    }
    result["served_via"] = "x402"
    return result
