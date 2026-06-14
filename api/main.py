"""
FastAPI backend for AgentRanker.
  GET  /api/leaderboard          -> ranked agents (BigQuery + RAGAS)
  POST /api/pay                  -> trust-gated payment via Hedera
  GET  /api/analytics            -> ecosystem-wide stats from BigQuery
  POST /api/autonomous-hire      -> full autonomous agent hiring loop (Feature 1)
  POST /api/x402/service         -> x402 pay-per-request handshake demo (Feature 2)
  GET  /api/x402/requirements    -> inspect 402 requirements for a resource

The frontend ONLY talks to these endpoints - never imports
integrations directly.
"""

from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from core.leaderboard import build_leaderboard, find_agent
from core.requester_agent import RequesterAgent
from core.scoring import score_all_agents
from core.services import compute_service_result

app = FastAPI(title="AgentRanker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/leaderboard")
def get_leaderboard(
    capability: Optional[str] = None,
    domain: Optional[str] = None,
    x402_only: bool = False,
):
    bq    = config.get_bigquery_client()
    ragas = config.get_ragas_client()

    agents = bq.get_erc8004_agents()
    ranked = build_leaderboard(
        agents, ragas,
        capability_filter=capability,
        domain_filter=domain,
        x402_only=x402_only,
    )

    return {
        "agents": [
            {
                **asdict(a),
                "trust_score":  a.trust_score,
                "ragas_average": a.ragas.average if a.ragas else None,
            }
            for a in ranked
        ],
        "source": {
            "bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock",
            "ragas":    "live" if config.USE_LIVE_RAGAS    else "mock",
        },
    }


@app.get("/api/domains")
def get_domains():
    """
    Return the domain taxonomy derived from on-chain AgentRegistered metadata.
    Live: decodes base64 JSON type URLs from BigQuery.
    Mock: reads pre-computed counts from fixtures.
    """
    bq = config.get_bigquery_client()
    taxonomy = bq.get_domain_taxonomy()
    return {
        "domains": taxonomy,
        "source": {"bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock"},
    }


class PayRequest(BaseModel):
    requester_id: str = "demo-user"
    target_agent_id: str
    amount_usd: Optional[float] = None


@app.post("/api/pay")
def pay_for_query(req: PayRequest):
    bq    = config.get_bigquery_client()
    ragas = config.get_ragas_client()

    agents = bq.get_erc8004_agents()
    ranked = build_leaderboard(agents, ragas)
    agent  = find_agent(ranked, req.target_agent_id)

    if agent is None:
        return {"error": f"agent {req.target_agent_id} not found"}

    hedera   = config.get_hedera_client()
    decision = hedera.submit_payment(
        requester_id=req.requester_id,
        target_agent_id=agent.agent_id,
        trust_score=agent.trust_score,
        threshold=config.TRUST_THRESHOLD,
        amount_usd=req.amount_usd or config.QUERY_FEE_USD,
    )

    return {
        "agent_name":         agent.name,
        "agent_hedera_topic": agent.hedera_topic_id,
        "decision":           asdict(decision),
        "source":             {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


@app.get("/api/analytics")
def get_analytics():
    bq = config.get_bigquery_client()
    stats = bq.get_ecosystem_stats()
    return {
        "stats": asdict(stats),
        "source": {"bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock"},
    }


class AutonomousHireRequest(BaseModel):
    goal: str = "I need a RAG pipeline evaluated"
    capability: str = "rag-evaluation"
    trust_threshold: Optional[float] = None   # defaults to config.TRUST_THRESHOLD
    narrate_with_llm: bool = False
    requester_id: str = "requester-agent-v1"
    amount_usd: Optional[float] = None
    transaction_type: str = "batch"           # "standard" | "batch" | "scheduled" | "atomic_swap"


@app.post("/api/autonomous-hire")
def autonomous_hire(req: AutonomousHireRequest):
    """
    Run the full autonomous agent-to-agent hiring loop and return a
    step-by-step trace of every decision the RequesterAgent made.

    The loop:
      1. DISCOVER  — load leaderboard (BigQuery + RAGAS)
      2. FILTER    — capability match + trust threshold
      3. SELECT    — highest-trust serviceable agent (is_serviceable=True preferred)
      4. DECIDE    — rule-based (or optional LLM-narrated) reasoning
      5. PAY       — trust-gated HBAR payment on Hedera; decision logged to HCS
      6. SERVE     — real x402 pay-per-request call; RAGAS live or labelled mock
    """
    bq     = config.get_bigquery_client()
    ragas  = config.get_ragas_client()
    hedera = config.get_hedera_client()
    x402   = config.get_x402_client()

    agent = RequesterAgent(
        goal=req.goal,
        capability=req.capability,
        trust_threshold=req.trust_threshold or config.TRUST_THRESHOLD,
        narrate_with_llm=req.narrate_with_llm,
        requester_id=req.requester_id,
        amount_usd=req.amount_usd or config.QUERY_FEE_USD,
        transaction_type=req.transaction_type,
    )
    result = agent.hire(bq, ragas, hedera, x402)

    return {
        **asdict(result),
        "source": {
            "bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock",
            "ragas":    "live" if config.USE_LIVE_RAGAS    else "mock",
            "hedera":   "live" if config.USE_LIVE_HEDERA   else "mock",
        },
    }


# ---------------------------------------------------------------------------
# x402 pay-per-request endpoints (Feature 2)
# ---------------------------------------------------------------------------

# Map x402 resource_id -> (capability, default_agent_id).
# The default agent is the curated serviceable agent used for the standalone
# /api/x402/service demo.  The hire loop uses the selected agent's own ID.
_X402_RESOURCE_MAP: dict = {
    "rag-eval":       ("rag-evaluation",  "agent-graphrag-eval"),
    "summarize":      ("summarization",   "agent-summarizer-pro"),
    "code-gen":       ("code-generation", "agent-codegen-sentinel"),
    "sec-audit":      ("security-audit",  "agent-sol-auditor"),
    "defi-data":      ("defi-analytics",  "agent-defi-oracle"),
    "compliance":     ("compliance",      "agent-compliance-guard"),
    "content":        ("content-writing", "agent-content-craft"),
    "smart-contract": ("smart-contract",  "agent-smartcont-builder"),
    "data-analysis":  ("data-analysis",   "agent-data-wizard"),
    "translate":      ("translation",     "agent-translate-ai"),
}

# Non-evaluation resources (static, no RAGAS)
_X402_STATIC: dict = {
    "agent-info": {
        "task":                 "capability_query",
        "capabilities":         ["rag-evaluation", "summarization"],
        "supported_protocols":  ["x402", "a2a"],
        "summary":              "Agent supports RAG evaluation and summarization via x402 pay-per-request.",
        "source":               "static",
    },
}


@app.get("/api/x402/requirements")
def x402_requirements(resource_id: str = "rag-eval"):
    """
    Return the x402 payment requirements for a protected resource —
    the machine-readable equivalent of an HTTP 402 response body.
    """
    x402 = config.get_x402_client()
    reqs = x402.get_payment_requirements(resource_id)
    return {
        "http_status_equivalent": 402,
        "requirements": reqs,
        "source": {"x402": "live" if config.USE_LIVE_X402 else "mock"},
    }


class X402ServiceRequest(BaseModel):
    resource_id: str = "rag-eval"
    requester_id: str = "requester-agent-v1"


@app.post("/api/x402/service")
def x402_service(req: X402ServiceRequest):
    """
    Run the complete x402 pay-per-request protocol flow and return a
    step-by-step trace of the 402 handshake:

      1. REQUEST      — client requests protected resource
      2. CHALLENGE    — server responds HTTP 402 with payment requirements
      3. PAYMENT      — client creates on-chain HBAR payment (Hedera testnet)
      4. VERIFICATION — server confirms payment on mirror node
      5. ACCESS       — server grants access and returns the resource

    This endpoint simulates both the client and server sides so the full
    protocol is visible in a single call — demo-friendly while preserving
    the real protocol semantics.
    """
    import time
    x402 = config.get_x402_client()
    steps = []
    t_start = time.monotonic()

    def ms() -> int:
        return int((time.monotonic() - t_start) * 1000)

    # ── 1. REQUEST ────────────────────────────────────────────────────
    steps.append({
        "step_type":   "request",
        "title":       "Client requests protected resource",
        "status":      "ok",
        "description": (
            f"GET /api/x402/service/{req.resource_id} — "
            "no payment header present."
        ),
        "data": {"resource_id": req.resource_id, "requester_id": req.requester_id},
        "elapsed_ms": ms(),
    })

    # ── 2. CHALLENGE (402) ────────────────────────────────────────────
    requirements = x402.get_payment_requirements(req.resource_id)
    scheme = requirements["schemes"][0]
    steps.append({
        "step_type":   "challenge",
        "title":       "Server: HTTP 402 Payment Required",
        "status":      "ok",
        "description": (
            f"Server returns 402 with x402/1 requirements. "
            f"Must pay {scheme['amount_tinybars']} tinybars "
            f"({scheme['amount_tinybars'] / 1e8:.5f} HBAR) to "
            f"{scheme['recipient']} on {scheme['network']}."
        ),
        "data": requirements,
        "elapsed_ms": ms(),
    })

    # ── 3. PAYMENT ────────────────────────────────────────────────────
    try:
        payment_proof = x402.submit_x402_payment(requirements, req.requester_id)
        steps.append({
            "step_type":   "payment",
            "title":       "Client: on-chain HBAR payment",
            "status":      "ok",
            "description": (
                f"Client creates Hedera TransferTransaction. "
                f"Tx: {payment_proof['tx_id']}. "
                f"Memo: {payment_proof['memo']}."
            ),
            "data": payment_proof,
            "elapsed_ms": ms(),
        })
    except Exception as exc:
        steps.append({
            "step_type":   "payment",
            "title":       "Client: payment failed",
            "status":      "error",
            "description": str(exc),
            "data":        {},
            "elapsed_ms":  ms(),
        })
        return {
            "resource_id": req.resource_id,
            "verified": False,
            "result": None,
            "steps": steps,
            "error": str(exc),
            "source": {"x402": "live" if config.USE_LIVE_X402 else "mock"},
        }

    # ── 4. VERIFICATION ───────────────────────────────────────────────
    verified, verify_reason = x402.verify_x402_payment(payment_proof, requirements)
    steps.append({
        "step_type":   "verification",
        "title":       "Server: verify payment on-chain",
        "status":      "ok" if verified else "blocked",
        "description": (
            f"Mirror node check: {verify_reason}. "
            f"Memo prefix ✓  |  Recipient ✓  |  Amount ✓"
            if verified else verify_reason
        ),
        "data": {
            "tx_id":   payment_proof.get("tx_id"),
            "verified": verified,
            "reason":  verify_reason,
        },
        "elapsed_ms": ms(),
    })

    if not verified:
        return {
            "resource_id": req.resource_id,
            "verified": False,
            "result": None,
            "steps": steps,
            "error": verify_reason,
            "source": {"x402": "live" if config.USE_LIVE_X402 else "mock"},
        }

    # ── 5. ACCESS ─────────────────────────────────────────────────────
    # Resolve service result through the shared compute_service_result()
    # path — same code that the SERVE step in the hire loop uses.
    if req.resource_id in _X402_STATIC:
        service_result = _X402_STATIC[req.resource_id]
    elif req.resource_id in _X402_RESOURCE_MAP:
        capability, default_agent_id = _X402_RESOURCE_MAP[req.resource_id]
        ragas = config.get_ragas_client()
        service_result = compute_service_result(capability, default_agent_id, ragas)
    else:
        service_result = {
            "task":    req.resource_id,
            "summary": f"Resource '{req.resource_id}' delivered.",
            "source":  "mock",
        }

    steps.append({
        "step_type":   "access",
        "title":       "Server: 200 OK — resource delivered",
        "status":      "ok",
        "description": (
            f"Payment verified. Access granted to '{req.resource_id}'. "
            f"Source: {service_result.get('source', 'unknown')}. "
            f"{service_result.get('summary', '')}"
        ),
        "data": service_result,
        "elapsed_ms": ms(),
    })

    return {
        "resource_id":   req.resource_id,
        "requirements":  requirements,
        "payment_proof": payment_proof,
        "verified":      True,
        "result":        service_result,
        "steps":         steps,
        "total_ms":      ms(),
        "source": {"x402": "live" if config.USE_LIVE_X402 else "mock"},
    }


# ---------------------------------------------------------------------------
# Scheduled re-evaluation endpoints (Feature 4)
# ---------------------------------------------------------------------------

class ScheduleReevalRequest(BaseModel):
    agent_id: str
    scheduled_by: str = "requester-agent-v1"


@app.post("/api/schedule/reevaluation")
def schedule_reevaluation(req: ScheduleReevalRequest):
    """
    Create a Hedera ScheduleCreateTransaction that wraps an HCS message
    committing the next re-evaluation of agent_id to the chain.

    Live mode:  posts a real ScheduleCreateTransaction to Hedera testnet.
                The schedule_id is queryable on HashScan forever.
    Mock mode:  returns a shaped response instantly (zero network calls).
    """
    hedera = config.get_hedera_client()
    result = hedera.schedule_reevaluation(req.agent_id, req.scheduled_by)
    return {
        "schedule": asdict(result),
        "source": {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


@app.get("/api/schedule/status/{schedule_id:path}")
def schedule_status(schedule_id: str):
    """
    Poll the current status of a Hedera scheduled re-evaluation
    (pending / executed / expired / deleted).

    Live mode:  queries testnet mirror node REST API.
    Mock mode:  returns "executed" immediately.
    """
    hedera = config.get_hedera_client()
    result = hedera.get_schedule_status(schedule_id)
    return {
        "schedule": asdict(result),
        "source": {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


# ---------------------------------------------------------------------------
# HCS-14 agent identity endpoints (Feature 5)
# ---------------------------------------------------------------------------

class RegisterIdentityRequest(BaseModel):
    agent_id: str
    name: str
    capabilities: list = ["rag-evaluation"]


@app.post("/api/identity/register")
def register_identity(req: RegisterIdentityRequest):
    """
    Register a new agent on HCS-14: create an HCS topic (the universal agent ID)
    with the identity JSON as the topic memo, then submit the genesis message.

    Live: real TopicCreateTransaction on Hedera testnet.
    Mock: instant fake topic ID + shaped response.
    """
    hedera = config.get_hedera_client()
    identity = hedera.register_agent_identity(req.agent_id, req.name, req.capabilities)
    return {
        "identity": asdict(identity),
        "source": {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


@app.get("/api/identity/{agent_id}")
def get_identity(agent_id: str):
    """
    Return the HCS-14 identity for a known agent, including its topic_id
    and the most recent audit log entries from that topic.
    """
    bq     = config.get_bigquery_client()
    hedera = config.get_hedera_client()

    agents = bq.get_erc8004_agents()
    agent  = next((a for a in agents if a.agent_id == agent_id), None)
    if agent is None:
        return {"error": f"agent {agent_id!r} not found"}

    topic_id = agent.hedera_topic_id or hedera.get_agent_identity(agent_id)
    audit_log = []
    if topic_id:
        entries = hedera.get_agent_audit_log(topic_id, limit=10)
        audit_log = [asdict(e) for e in entries]

    return {
        "agent_id":   agent_id,
        "name":       agent.name,
        "topic_id":   topic_id,
        "audit_log":  audit_log,
        "source":     {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


@app.get("/api/identity/{agent_id}/audit")
def get_audit_log(agent_id: str, topic_id: Optional[str] = None, limit: int = 25):
    """
    Fetch the full audit log for an agent from its HCS identity topic.
    Pass topic_id explicitly, or it will be resolved from the agent registry.
    """
    bq     = config.get_bigquery_client()
    hedera = config.get_hedera_client()

    if topic_id is None:
        agents = bq.get_erc8004_agents()
        agent  = next((a for a in agents if a.agent_id == agent_id), None)
        topic_id = (agent.hedera_topic_id if agent else None) or hedera.get_agent_identity(agent_id)

    if not topic_id:
        return {"error": f"no HCS topic found for agent {agent_id!r}", "entries": []}

    entries = hedera.get_agent_audit_log(topic_id, limit=limit)
    return {
        "agent_id":   agent_id,
        "topic_id":   topic_id,
        "entries":    [asdict(e) for e in entries],
        "count":      len(entries),
        "source":     {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


@app.post("/api/identity/{agent_id}/log-event")
def log_identity_event(agent_id: str, event_type: str, payload: dict):
    """Submit a custom event to the agent's HCS identity topic."""
    bq     = config.get_bigquery_client()
    hedera = config.get_hedera_client()

    agents   = bq.get_erc8004_agents()
    agent    = next((a for a in agents if a.agent_id == agent_id), None)
    topic_id = (agent.hedera_topic_id if agent else None) or hedera.get_agent_identity(agent_id)

    if not topic_id:
        return {"error": f"no HCS topic found for agent {agent_id!r}"}

    seq = hedera.log_agent_event(topic_id, event_type, payload)
    return {
        "topic_id":        topic_id,
        "sequence_number": seq,
        "source":          {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


@app.get("/api/ranking/comparison")
def ranking_comparison():
    """
    Return side-by-side naive vs. Sybil-resistant ranking for all agents
    that have on-chain feedback data.  The response includes per-agent
    rank deltas so the frontend can render the hero visual contrast.
    """
    bq = config.get_bigquery_client()
    feedbacks = bq.get_feedback_for_scoring()
    if not feedbacks:
        return {
            "comparison": None,
            "error": "No feedback data available.",
            "source": {"bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock"},
        }

    giver_addresses = list({fb.giver_address for fb in feedbacks})
    giver_stats = bq.get_giver_wallet_stats(giver_addresses)
    comparison = score_all_agents(feedbacks, giver_stats)

    return {
        "comparison": asdict(comparison),
        "source": {"bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock"},
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "config": {
            "hedera":    "live" if config.USE_LIVE_HEDERA   else "mock",
            "bigquery":  "live" if config.USE_LIVE_BIGQUERY else "mock",
            "ragas":     "live" if config.USE_LIVE_RAGAS    else "mock",
            "x402":      "live" if config.USE_LIVE_X402     else "mock",
            "trust_threshold": config.TRUST_THRESHOLD,
        },
    }
