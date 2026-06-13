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

import json
import os
from pathlib import Path
from typing import Dict, List

from google.cloud import bigquery

from integrations.bigquery.base import BigQueryClient
from core.models import Agent, EcosystemStats
from core.scoring import FeedbackEvent, GiverStats

WALLET_CACHE = Path(__file__).parent.parent.parent / "fixtures" / "wallet_stats_cache.json"

IDENTITY_REGISTRY    = "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432"
REPUTATION_REGISTRY  = "0x8004baa17c55a88189ae136b182e5fda19de9b63"
TRANSFER_TOPIC       = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO_TOPIC           = "0x0000000000000000000000000000000000000000000000000000000000000000"
FEEDBACK_TOPIC       = "0x6a4a61743519c9d648a14e6493f47dbe3ff1aa29e7785c96c8326a205e58febc"

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

    def get_domain_taxonomy(self) -> Dict[str, int]:
        """
        Decode AgentRegistered events to extract the `type` URL from
        each agent's base64-encoded JSON metadata, then normalize the
        URL fragment into a human-readable domain name.

        Full topic hash was confirmed as 0xca52e62c... in dataset_findings.md.
        We use a LIKE prefix match since the tail bytes weren't stored.
        Scans ~20 MB (IdentityRegistry events only).
        """
        sql = f"""
        WITH raw AS (
          SELECT
            REGEXP_EXTRACT(
              SAFE_CONVERT_BYTES_TO_STRING(FROM_HEX(SUBSTR(data, 3))),
              r'data:application/json;base64,([A-Za-z0-9+/=]+)'
            ) AS b64
          FROM `bigquery-public-data.crypto_ethereum.logs`
          WHERE address = '{IDENTITY_REGISTRY}'
            AND topics[SAFE_OFFSET(0)] LIKE '0xca52%'
            AND data IS NOT NULL
            AND LENGTH(data) > 10
          LIMIT 5000
        ),
        decoded AS (
          SELECT
            JSON_EXTRACT_SCALAR(
              SAFE_CONVERT_BYTES_TO_STRING(FROM_BASE64(b64)), '$.type'
            ) AS type_url
          FROM raw
          WHERE b64 IS NOT NULL
        )
        SELECT
          COALESCE(
            REGEXP_EXTRACT(type_url, r'#([a-zA-Z0-9_\\-]+)$'),
            'Unclassified'
          ) AS domain_fragment,
          COUNT(*) AS agent_count
        FROM decoded
        GROUP BY domain_fragment
        ORDER BY agent_count DESC
        """
        # Domain fragment → normalized name mapping
        NORMALISE = {
            "registration-v1":  "General",
            "rag-evaluation":   "RAG & Retrieval",
            "RAG-evaluation":   "RAG & Retrieval",
            "rag":              "RAG & Retrieval",
            "summarization":    "Summarization",
            "code-review":      "Code Review",
            "data-analysis":    "Data Analysis",
            "Unclassified":     "Unclassified",
        }
        try:
            rows = list(self.client.query(sql).result())
        except Exception:
            return {}

        taxonomy: Dict[str, int] = {}
        for row in rows:
            name = NORMALISE.get(row.domain_fragment, row.domain_fragment or "Unclassified")
            taxonomy[name] = taxonomy.get(name, 0) + int(row.agent_count)
        return taxonomy

    def get_feedback_for_scoring(self) -> List[FeedbackEvent]:
        """
        Pull all FeedbackGiven events with decoded quality scores (ABI slot1)
        and giver addresses (topics[2]).  Scans ~50 MB — cheap.
        """
        sql = f"""
        SELECT
          topics[SAFE_OFFSET(1)] AS agent_id_hex,
          LOWER(CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], -40))) AS giver_address,
          SAFE_CAST(
            CONCAT('0x', RIGHT(SUBSTR(data, 3,  64), 16)) AS INT64
          ) AS vote_weight,
          SAFE_CAST(
            CONCAT('0x', RIGHT(SUBSTR(data, 67, 64), 16)) AS INT64
          ) AS quality_score,
          block_timestamp
        FROM `bigquery-public-data.crypto_ethereum.logs`
        WHERE address = '{REPUTATION_REGISTRY}'
          AND topics[SAFE_OFFSET(0)] = '{FEEDBACK_TOPIC}'
          AND topics[SAFE_OFFSET(2)] IS NOT NULL
          AND data IS NOT NULL
          AND LENGTH(data) >= 131
        """
        try:
            rows = list(self.client.query(sql).result())
        except Exception:
            return []

        events: List[FeedbackEvent] = []
        for row in rows:
            q = float(row.quality_score or 0)
            if not (0 <= q <= 100):
                continue
            events.append(FeedbackEvent(
                agent_id=str(row.agent_id_hex or ""),
                giver_address=str(row.giver_address or ""),
                quality_score=q,
                vote_weight=float(row.vote_weight or 1),
                timestamp=str(row.block_timestamp),
            ))
        return events

    def get_giver_wallet_stats(
        self, giver_addresses: List[str]
    ) -> Dict[str, GiverStats]:
        """
        Get wallet age and tx count for each giver.  First loads any cached
        stats from fixtures/wallet_stats_cache.json to avoid redundant BigQuery
        scans; only fetches missing addresses from BigQuery.

        Full scan costs ~$9 for 627 addresses — run once with
        scripts/fetch_scoring_data.py and the cache covers all future demos.
        """
        # Load cache
        cached: Dict[str, GiverStats] = {}
        if WALLET_CACHE.exists():
            with open(WALLET_CACHE) as f:
                raw = json.load(f).get("wallet_stats", {})
            for addr, stats in raw.items():
                cached[addr] = GiverStats(**stats)

        missing = [a for a in giver_addresses if a not in cached]
        if not missing:
            return {a: cached[a] for a in giver_addresses if a in cached}

        # Fetch missing addresses from BigQuery (batched)
        placeholders = ", ".join(f"'{a}'" for a in missing[:500])
        sql = f"""
        SELECT
          from_address,
          TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MIN(block_timestamp), DAY) AS wallet_age_days,
          COUNT(*) AS tx_count
        FROM `bigquery-public-data.crypto_ethereum.transactions`
        WHERE from_address IN ({placeholders})
        GROUP BY from_address
        """
        try:
            rows = list(self.client.query(sql).result())
            for row in rows:
                cached[row.from_address] = GiverStats(
                    wallet_age_days=float(row.wallet_age_days or 0),
                    tx_count=int(row.tx_count or 0),
                )
        except Exception:
            pass

        return {a: cached[a] for a in giver_addresses if a in cached}