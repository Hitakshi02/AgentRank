"""
Core data models for AgentRanker.
Pure Python dataclasses - no external dependencies.
Every integration (mock or live) must return data shaped exactly like these.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RagasScores:
    faithfulness: float
    answer_relevancy: float
    context_precision: float

    @property
    def average(self) -> float:
        return round(
            (self.faithfulness + self.answer_relevancy + self.context_precision) / 3,
            3,
        )


@dataclass
class Agent:
    agent_id: str                  # e.g. "0xabc...1234" or internal id
    name: str                      # human readable, e.g. "GraphRAG Evaluator"
    description: str
    capability: str                # e.g. "rag-evaluation"
    hedera_topic_id: Optional[str] = None     # HCS-14 universal agent id (topic)
    erc8004_address: Optional[str] = None     # on-chain identity on Ethereum
    erc8004_reputation: Optional[float] = None  # 0-100, from BigQuery
    supports_x402: bool = False
    ragas: Optional[RagasScores] = None

    @property
    def trust_score(self) -> float:
        """
        Combined trust score blending on-chain reputation (BigQuery / ERC-8004)
        and live evaluation quality (RAGAS via Hedera).
        Both are optional; falls back gracefully.
        """
        parts = []
        if self.erc8004_reputation is not None:
            parts.append(self.erc8004_reputation / 100.0)
        if self.ragas is not None:
            parts.append(self.ragas.average)
        if not parts:
            return 0.0
        return round(sum(parts) / len(parts), 3)


@dataclass
class PaymentDecision:
    requester_id: str
    target_agent_id: str
    trust_score: float
    threshold: float
    approved: bool
    amount_usd: float
    tx_id: Optional[str] = None          # Hedera tx id if approved
    hcs_message_id: Optional[str] = None  # audit log message id
    reason: str = ""


@dataclass
class EcosystemStats:
    total_agents: int
    agents_with_x402: int
    avg_reputation: float
    registrations_last_30d: int
    reputation_distribution: dict = field(default_factory=dict)
    # e.g. {"0-20": 120, "20-40": 340, ...}
