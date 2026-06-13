"""
Leaderboard business logic.
Operates purely on core.models.Agent - doesn't know about Hedera,
BigQuery, or RAGAS specifically. Combines data from whatever clients
config.py hands it.
"""

from typing import List, Optional
from core.models import Agent


def build_leaderboard(
    bigquery_agents: List[Agent],
    ragas_client,
    capability_filter: Optional[str] = None,
) -> List[Agent]:
    """
    Take agents from BigQuery (with erc8004_reputation already set),
    enrich with RAGAS scores, and return sorted by trust_score desc.
    """
    enriched = []
    for agent in bigquery_agents:
        if capability_filter and agent.capability != capability_filter:
            continue
        if agent.ragas is None:
            agent.ragas = ragas_client.evaluate(agent.agent_id)
        enriched.append(agent)

    return sorted(enriched, key=lambda a: a.trust_score, reverse=True)


def find_agent(agents: List[Agent], agent_id: str) -> Optional[Agent]:
    for a in agents:
        if a.agent_id == agent_id:
            return a
    return None
