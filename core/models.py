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
    domain: Optional[str] = None             # on-chain domain hint (from AgentRegistered type URL)

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
    tx_id: Optional[str] = None           # Hedera tx id OR Arc 0x tx hash
    hcs_message_id: Optional[str] = None  # audit log message id (Hedera only)
    reason: str = ""
    rail: str = "hedera"                  # "hedera" | "arc"
    usdc_amount: Optional[float] = None   # set when rail="arc"


@dataclass
class EcosystemStats:
    total_agents: int
    agents_with_x402: int
    avg_reputation: float
    registrations_last_30d: int
    reputation_distribution: dict = field(default_factory=dict)
    # e.g. {"0-20": 120, "20-40": 340, ...}


@dataclass
class X402AccessResult:
    """Full trace of one x402 pay-per-request handshake."""
    resource_id: str
    requirements: Optional[dict] = None    # the 402 payment requirements
    payment_proof: Optional[dict] = None   # what was paid
    verified: bool = False
    result: Optional[dict] = None          # the service response (if verified)
    source: str = "mock"                   # "mock" or "live"
    error: Optional[str] = None
    # Human-readable trace of each protocol step
    steps: list = field(default_factory=list)  # List[dict] — step_type/title/status/description


@dataclass
class HireStep:
    step_type: str    # discover | filter | select | decide | pay | serve
    title: str
    status: str       # ok | blocked | error
    description: str
    data: dict = field(default_factory=dict)
    elapsed_ms: int = 0


@dataclass
class AuditLogEntry:
    """A single HCS message in an agent's audit trail."""
    sequence_number: int
    consensus_timestamp: str        # Hedera consensus timestamp (Unix seconds.nanos)
    event_type: str                 # registration | hire | payment | reevaluation | x402_access
    payload: dict = field(default_factory=dict)
    topic_id: str = ""


@dataclass
class AgentIdentity:
    """HCS-14 agent identity record backed by an HCS topic."""
    agent_id: str
    name: str
    topic_id: str                   # the HCS topic IS the universal agent ID
    capabilities: list = field(default_factory=list)
    registered_at: Optional[str] = None
    memo: str = ""                  # JSON-encoded HCS-14 metadata stored as topic memo
    audit_log: list = field(default_factory=list)   # List[AuditLogEntry]
    error: Optional[str] = None


@dataclass
class ScheduledReevaluation:
    """Result of creating a Hedera Scheduled Transaction for agent re-evaluation."""
    schedule_id: str              # e.g. "0.0.12345"
    agent_id: str
    scheduled_by: str
    hcs_topic_id: str
    memo: str
    status: str = "pending"       # pending | executed | expired | deleted
    executed_at: Optional[str] = None
    expiration_time: Optional[str] = None
    hcs_sequence_number: Optional[int] = None
    error: Optional[str] = None


@dataclass
class AutonomousHireResult:
    goal: str
    capability: str
    steps: list = field(default_factory=list)          # List[HireStep]
    selected_agent_id: Optional[str] = None
    selected_agent_name: Optional[str] = None
    payment_decision: Optional[dict] = None            # PaymentDecision serialised
    service_output: Optional[dict] = None
    total_elapsed_ms: int = 0
    success: bool = False
    error: Optional[str] = None
