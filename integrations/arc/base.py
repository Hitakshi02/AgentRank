"""
Abstract interface for Arc (Circle's stablecoin L1) integration.
live.py  — real ERC-20 USDC transfer on Arc testnet via web3.py
mock.py  — instant fake, shaped identically, never fails

Arc testnet specs (confirmed from Circle docs):
  Chain ID : 5042002
  RPC      : https://rpc.testnet.arc.network
  USDC     : 0x3600000000000000000000000000000000000000
  Faucet   : https://faucet.circle.com/  (select "Arc Testnet")

USDC is the native gas token on Arc — transfers pay gas in USDC.
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.models import PaymentDecision


class ArcClient(ABC):

    @abstractmethod
    def settle_usdc_payment(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usdc: float,
        recipient_address: Optional[str] = None,
    ) -> PaymentDecision:
        """
        Evaluate the trust gate and, if approved, transfer USDC on Arc testnet.
        Returns a PaymentDecision with rail="arc".
        Trust gate is identical to the Hedera rail so the two are swappable.
        """
        ...

    @abstractmethod
    def get_usdc_balance(self, address: str) -> float:
        """Return USDC balance (in human-readable USDC, not wei) for address."""
        ...
