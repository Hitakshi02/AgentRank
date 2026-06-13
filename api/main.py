"""
FastAPI backend for AgentRanker.
Exposes 3 endpoints, one per frontend tab:
  GET  /api/leaderboard          -> ranked agents (BigQuery + RAGAS)
  POST /api/pay                  -> trust-gated payment via Hedera
  GET  /api/analytics             -> ecosystem-wide stats from BigQuery

The frontend ONLY talks to these endpoints - never imports
integrations directly. This keeps every tab independently
removable/replaceable.
"""

from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from core.leaderboard import build_leaderboard, find_agent

app = FastAPI(title="AgentRanker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/leaderboard")
def get_leaderboard(capability: Optional[str] = None):
    bq = config.get_bigquery_client()
    ragas = config.get_ragas_client()

    agents = bq.get_erc8004_agents()
    ranked = build_leaderboard(agents, ragas, capability_filter=capability)

    return {
        "agents": [
            {
                **asdict(a),
                "trust_score": a.trust_score,
                "ragas_average": a.ragas.average if a.ragas else None,
            }
            for a in ranked
        ],
        "source": {
            "bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock",
            "ragas": "live" if config.USE_LIVE_RAGAS else "mock",
        },
    }


class PayRequest(BaseModel):
    requester_id: str = "demo-user"
    target_agent_id: str
    amount_usd: Optional[float] = None


@app.post("/api/pay")
def pay_for_query(req: PayRequest):
    bq = config.get_bigquery_client()
    ragas = config.get_ragas_client()
    hedera = config.get_hedera_client()

    agents = bq.get_erc8004_agents()
    ranked = build_leaderboard(agents, ragas)
    agent = find_agent(ranked, req.target_agent_id)

    if agent is None:
        return {"error": f"agent {req.target_agent_id} not found"}

    decision = hedera.submit_payment(
        requester_id=req.requester_id,
        target_agent_id=agent.agent_id,
        trust_score=agent.trust_score,
        threshold=config.TRUST_THRESHOLD,
        amount_usd=req.amount_usd or config.QUERY_FEE_USD,
    )

    return {
        "agent_name": agent.name,
        "agent_hedera_topic": agent.hedera_topic_id,
        "decision": asdict(decision),
        "source": {"hedera": "live" if config.USE_LIVE_HEDERA else "mock"},
    }


@app.get("/api/analytics")
def get_analytics():
    bq = config.get_bigquery_client()
    stats = bq.get_ecosystem_stats()
    return {
        "stats": asdict(stats),
        "source": {"bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock"},
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "config": {
            "hedera": "live" if config.USE_LIVE_HEDERA else "mock",
            "bigquery": "live" if config.USE_LIVE_BIGQUERY else "mock",
            "ragas": "live" if config.USE_LIVE_RAGAS else "mock",
            "trust_threshold": config.TRUST_THRESHOLD,
        },
    }
