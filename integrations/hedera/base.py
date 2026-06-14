"""
Abstract interface for Hedera integration.
live.py implements this with real Hedera SDK calls.
mock.py implements this with instant fake responses.
Frontend/API code should only depend on this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.models import PaymentDecision, ScheduledReevaluation, AgentIdentity, AuditLogEntry
from typing import List


class HederaClient(ABC):

    @abstractmethod
    def get_agent_identity(self, agent_id: str) -> Optional[str]:
        """Return the HCS-14 topic id (universal agent id) for an agent, or None."""
        ...

    @abstractmethod
    def submit_payment(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usd: float,
    ) -> PaymentDecision:
        """
        Evaluate the trust gate and, if approved, execute an x402 payment
        on Hedera testnet. Always logs the decision to HCS regardless
        of outcome (approved or blocked).
        """
        ...

    @abstractmethod
    def log_to_hcs(self, message: dict) -> str:
        """Submit a message to an HCS topic for the audit trail. Returns message id."""
        ...

    @abstractmethod
    def schedule_reevaluation(
        self, agent_id: str, scheduled_by: str
    ) -> ScheduledReevaluation:
        """
        Create a Hedera ScheduleCreateTransaction that wraps an HCS message
        announcing a future re-evaluation of agent_id.  Returns a
        ScheduledReevaluation with the on-chain schedule_id so the caller
        can poll its status via the mirror node.
        """
        ...

    @abstractmethod
    def get_schedule_status(self, schedule_id: str) -> ScheduledReevaluation:
        """
        Query the current status of a previously created scheduled transaction
        (executed / pending / expired) via ScheduleInfoQuery or mirror node REST.
        """
        ...

    @abstractmethod
    def register_agent_identity(
        self,
        agent_id: str,
        name: str,
        capabilities: list,
    ) -> AgentIdentity:
        """
        Create an HCS topic whose memo encodes the HCS-14 agent identity JSON.
        The returned topic_id IS the universal agent identifier.
        Also submits a "registration" event to the new topic as the genesis message.
        """
        ...

    @abstractmethod
    def get_agent_audit_log(
        self, topic_id: str, limit: int = 25
    ) -> List[AuditLogEntry]:
        """
        Fetch the most recent HCS messages from an agent's identity topic.
        Live: queries testnet.mirrornode.hedera.com/api/v1/topics/{topic_id}/messages.
        Mock: reads from fixtures/audit_log_cache.json.
        """
        ...

    @abstractmethod
    def log_agent_event(
        self, topic_id: str, event_type: str, payload: dict
    ) -> str:
        """
        Submit a structured event to an agent's HCS topic.
        Returns the sequence number as a string.
        """
        ...

    def batch_hire(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usd: float,
        agent_topic_id: str = None,
    ) -> PaymentDecision:
        """
        HIP-551 Batch Transaction: atomically bundles HBAR transfer + HCS audit +
        agent topic log in one atomic tx. ACID guarantees.
        """
        ...

    def schedule_hire(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usd: float,
        execute_at_seconds: int = None,
    ) -> PaymentDecision:
        """
        Scheduled Transaction: async multi-sig coordination. Queues the hire
        for future execution.
        """
        ...

    def atomic_swap_hire(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usd: float,
    ) -> PaymentDecision:
        """
        Atomic Swap: simultaneous HBAR-for-service exchange. Both sides execute atomically.
        """
        ...
