"""
Mock BigQuery implementation.
Reads agent + ecosystem data from fixtures/agents.json.
Reads scoring data from fixtures/feedback_cache.json and
fixtures/wallet_stats_cache.json.
Shapes responses identically to live.py.
"""

import json
from pathlib import Path
from typing import Dict, List
from integrations.bigquery.base import BigQueryClient
from core.models import Agent, RagasScores, EcosystemStats
from core.scoring import FeedbackEvent, GiverStats

FIXTURES_PATH   = Path(__file__).parent.parent.parent / "fixtures" / "agents.json"
FEEDBACK_CACHE  = Path(__file__).parent.parent.parent / "fixtures" / "feedback_cache.json"
WALLET_CACHE    = Path(__file__).parent.parent.parent / "fixtures" / "wallet_stats_cache.json"


def _load_fixtures():
    with open(FIXTURES_PATH) as f:
        return json.load(f)


class MockBigQueryClient(BigQueryClient):

    def get_erc8004_agents(self) -> List[Agent]:
        data = _load_fixtures()
        agents = []
        for a in data["agents"]:
            ragas = None
            if a.get("ragas"):
                ragas = RagasScores(**a["ragas"])
            agents.append(
                Agent(
                    agent_id=a["agent_id"],
                    name=a["name"],
                    description=a["description"],
                    capability=a["capability"],
                    domain=a.get("domain"),
                    hedera_topic_id=a.get("hedera_topic_id"),
                    erc8004_address=a.get("erc8004_address"),
                    erc8004_reputation=a.get("erc8004_reputation"),
                    supports_x402=a.get("supports_x402", False),
                    is_serviceable=a.get("is_serviceable", False),
                    ragas=ragas,
                )
            )
        return agents

    def get_ecosystem_stats(self) -> EcosystemStats:
        data = _load_fixtures()
        stats = data["ecosystem_stats"]
        return EcosystemStats(
            total_agents=stats["total_agents"],
            agents_with_x402=stats["agents_with_x402"],
            avg_reputation=stats["avg_reputation"],
            registrations_last_30d=stats["registrations_last_30d"],
            reputation_distribution=stats["reputation_distribution"],
        )

    def get_domain_taxonomy(self) -> Dict[str, int]:
        data = _load_fixtures()
        return data.get("domain_taxonomy", {})

    def get_feedback_for_scoring(self) -> List[FeedbackEvent]:
        if not FEEDBACK_CACHE.exists():
            return []
        with open(FEEDBACK_CACHE) as f:
            data = json.load(f)
        return [FeedbackEvent(**e) for e in data.get("feedback_events", [])]

    def get_giver_wallet_stats(
        self, giver_addresses: List[str]
    ) -> Dict[str, GiverStats]:
        if not WALLET_CACHE.exists():
            return {}
        with open(WALLET_CACHE) as f:
            data = json.load(f)
        stats = data.get("wallet_stats", {})
        return {
            addr: GiverStats(**stats[addr])
            for addr in giver_addresses
            if addr in stats
        }
