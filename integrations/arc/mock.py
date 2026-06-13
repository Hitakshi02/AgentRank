"""
Mock Arc implementation.
Returns instantly, no network calls, no Arc account needed.
Shapes responses identically to live.py so the rest of the app
never needs to know which is active.
"""

import random
import time
from typing import Optional

from integrations.arc.base import ArcClient
from core.models import PaymentDecision


def _fake_arc_tx() -> str:
    # Arc tx hashes are standard EVM 0x-prefixed 32-byte hex
    return "0x" + "".join(random.choices("0123456789abcdef", k=64))


def _fake_arc_address() -> str:
    return "0x" + "".join(random.choices("0123456789abcdef", k=40))


class MockArcClient(ArcClient):

    def settle_usdc_payment(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usdc: float,
        recipient_address: Optional[str] = None,
    ) -> PaymentDecision:
        approved = trust_score >= threshold
        return PaymentDecision(
            requester_id=requester_id,
            target_agent_id=target_agent_id,
            trust_score=trust_score,
            threshold=threshold,
            approved=approved,
            amount_usd=amount_usdc,
            usdc_amount=amount_usdc,
            tx_id=_fake_arc_tx() if approved else None,
            hcs_message_id=None,
            reason=(
                f"trust_score {trust_score:.3f} >= threshold {threshold:.3f} — "
                f"USDC ${amount_usdc:.4f} transferred on Arc testnet"
                if approved
                else f"trust_score {trust_score:.3f} < threshold {threshold:.3f} — payment blocked"
            ),
            rail="arc",
        )

    def get_usdc_balance(self, address: str) -> float:
        return round(random.uniform(5.0, 50.0), 6)
