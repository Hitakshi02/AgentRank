"""
Abstract interface for Hedera integration.
live.py implements this with real Hedera SDK calls.
mock.py implements this with instant fake responses.
Frontend/API code should only depend on this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.models import PaymentDecision


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
