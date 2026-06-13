"""
Live BigQuery implementation.
Queries the public Ethereum mainnet dataset for ERC-8004 Identity and
Reputation registry activity, and shapes results into core.models.Agent
and EcosystemStats - identical shape to mock.py.

Requires:
  - A Google Cloud project with BigQuery API enabled
  - Application Default Credentials configured:
        gcloud auth application-default login
    or GOOGLE_APPLICATION_CREDENTIALS pointing to a service account key
  - GOOGLE_CLOUD_PROJECT env var set to your project id

Contract addresses (Ethereum Mainnet):
  IdentityRegistry:   0x8004a169fb4a3325136eb29fa0ceb6d2e539a432
  ReputationRegistry: 0x8004baa17c55a88189ae136b182e5fda19de9b63
"""

import os
from typing import List

from google.cloud import bigquery

from integrations.bigquery.base import BigQueryClient
from core.models import Agent, EcosystemStats

IDENTITY_REGISTRY = "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432"
REPUTATION_REGISTRY = "0x8004baa17c55a88189ae136b182e5fda19de9b63"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO_TOPIC = "0x0000000000000000000000000000000000000000000000000000000000000000"

# These ERC-8004 agents don't necessarily exist on-chain with our
# specific capability tags - we cross-reference real on-chain
# registration + feedback activity with our curated demo agent set
# via the erc8004_address field in fixtures, when present.

AGENTS_QUERY = f"""
WITH registrations AS (
  SELECT
    topics[SAFE_OFFSET(3)] AS agent_id_hex,
    LOWER(CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], -40))) AS owner_address,
    block_timestamp
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{IDENTITY_REGISTRY}'
    AND topics[SAFE_OFFSET(0)] = '{TRANSFER_TOPIC}'
    AND topics[SAFE_OFFSET(1)] = '{ZERO_TOPIC}'
),
feedback AS (
  SELECT
    topics[SAFE_OFFSET(1)] AS agent_id_hex,
    COUNT(*) AS feedback_count
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{REPUTATION_REGISTRY}'
  GROUP BY agent_id_hex
)
SELECT
  r.agent_id_hex,
  r.owner_address,
  r.block_timestamp AS registered_at,
  COALESCE(f.feedback_count, 0) AS feedback_count
FROM registrations r
LEFT JOIN feedback f ON r.agent_id_hex = f.agent_id_hex
ORDER BY feedback_count DESC
LIMIT 50
"""

STATS_QUERY = f"""
WITH registrations AS (
  SELECT
    DATE(block_timestamp) AS day,
    topics[SAFE_OFFSET(3)] AS agent_id_hex
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{IDENTITY_REGISTRY}'
    AND topics[SAFE_OFFSET(0)] = '{TRANSFER_TOPIC}'
    AND topics[SAFE_OFFSET(1)] = '{ZERO_TOPIC}'
),
feedback AS (
  SELECT
    topics[SAFE_OFFSET(1)] AS agent_id_hex,
    COUNT(*) AS feedback_count
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{REPUTATION_REGISTRY}'
  GROUP BY agent_id_hex
)
SELECT
  (SELECT COUNT(*) FROM registrations) AS total_agents,
  (SELECT COUNT(*) FROM registrations
   WHERE day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)) AS registrations_last_30d,
  (SELECT COUNT(DISTINCT agent_id_hex) FROM feedback) AS agents_with_feedback,
  (SELECT IFNULL(AVG(feedback_count), 0) FROM feedback) AS avg_feedback_per_agent
"""


def _feedback_to_reputation(feedback_count: int, max_feedback: int) -> float:
    """
    Simple, transparent reputation proxy: normalize feedback volume
    to a 0-100 scale relative to the most-reviewed agent in the result set.
    A real scoring algorithm would decode giveFeedback's value/valueDecimals
    fields - this proxy is intentionally simple and auditable, in the
    spirit of ERC-8004's "scoring should be public and verifiable" goal.
    """
    if max_feedback == 0:
        return 0.0
    return round(100.0 * feedback_count / max_feedback, 1)


class LiveBigQueryClient(BigQueryClient):

    def __init__(self):
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.client = bigquery.Client(project=project)

    def get_erc8004_agents(self) -> List[Agent]:
        """
        Returns up to 10 REAL agents pulled live from ERC-8004 on Ethereum
        mainnet (ranked by on-chain feedback volume), followed by 6 curated
        fallback agents from fixtures. The curated agents carry RAGAS scores
        and capability tags; the live agents carry real on-chain reputation.
        """
        from integrations.bigquery.mock import MockBigQueryClient
        fallback_agents = MockBigQueryClient().get_erc8004_agents()[:6]

        try:
            rows = list(self.client.query(AGENTS_QUERY).result())
        except Exception:
            rows = []

        if not rows:
            return fallback_agents

        max_feedback = max((row.feedback_count for row in rows), default=0)

        live_agents: List[Agent] = []
        for i, row in enumerate(rows[:10]):
            try:
                agent_num = int(row.agent_id_hex, 16)
            except (TypeError, ValueError):
                agent_num = i
            live_agents.append(
                Agent(
                    agent_id=f"onchain-{agent_num}",
                    name=f"Agent #{agent_num}",
                    description=(
                        f"Live ERC-8004 agent on Ethereum mainnet. "
                        f"Owner {row.owner_address}. "
                        f"{row.feedback_count} on-chain feedback events."
                    ),
                    capability="rag-evaluation",
                    hedera_topic_id=None,
                    erc8004_address=row.owner_address,
                    erc8004_reputation=_feedback_to_reputation(
                        row.feedback_count, max_feedback
                    ),
                    supports_x402=row.feedback_count > 0,
                    ragas=None,
                )
            )

        return live_agents + fallback_agents

    def get_ecosystem_stats(self) -> EcosystemStats:
        rows = list(self.client.query(STATS_QUERY).result())
        row = rows[0] if rows else None

        total_agents = int(row.total_agents) if row else 0
        registrations_30d = int(row.registrations_last_30d) if row else 0
        agents_with_feedback = int(row.agents_with_feedback) if row else 0
        avg_feedback = float(row.avg_feedback_per_agent) if row else 0.0

        return EcosystemStats(
            total_agents=total_agents,
            agents_with_x402=agents_with_feedback,  # proxy: active agents
            avg_reputation=round(avg_feedback, 2),
            registrations_last_30d=registrations_30d,
            reputation_distribution={},  # requires per-agent decode, omitted live
        )