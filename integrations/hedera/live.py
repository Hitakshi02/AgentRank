"""
Live Hedera implementation.
Executes real transactions on Hedera Testnet:
  - HBAR transfer (the "payment") via TransferTransaction
  - HCS message submit (the audit log) via TopicMessageSubmitTransaction

Requires .env with:
  HEDERA_OPERATOR_ID, HEDERA_OPERATOR_KEY,
  HEDERA_AGENT_ACCOUNT_ID, HEDERA_HCS_TOPIC_ID

Shapes its responses identically to mock.py.
"""

import os
import json
import time
from typing import Optional

from hiero_sdk_python import (
    Client,
    Network,
    AccountId,
    PrivateKey,
    TopicId,
    TransferTransaction,
    TopicMessageSubmitTransaction,
    Hbar,
)

from integrations.hedera.base import HederaClient
from core.models import PaymentDecision

# Small fixed HBAR amount for the demo "payment" - real money movement,
# trivial value. 1 tinybar = 0.00000001 HBAR.
DEMO_PAYMENT_TINYBARS = 100_000  # 0.001 HBAR


def _get_client() -> Client:
    operator_id = AccountId.from_string(os.environ["HEDERA_OPERATOR_ID"])
    operator_key = PrivateKey.from_string(os.environ["HEDERA_OPERATOR_KEY"])
    client = Client(Network(network="testnet"))
    client.set_operator(operator_id, operator_key)
    return client


class LiveHederaClient(HederaClient):

    def __init__(self):
        self.client = _get_client()
        self.operator_id = AccountId.from_string(os.environ["HEDERA_OPERATOR_ID"])
        self.operator_key = PrivateKey.from_string(os.environ["HEDERA_OPERATOR_KEY"])
        self.agent_account_id = AccountId.from_string(os.environ["HEDERA_AGENT_ACCOUNT_ID"])
        self.topic_id = TopicId.from_string(os.environ["HEDERA_HCS_TOPIC_ID"])

    def get_agent_identity(self, agent_id: str) -> Optional[str]:
        # HCS-14 universal agent identity is a stretch goal - for now,
        # all agents share the audit topic. Returning the topic id
        # signals "this agent has a Hedera presence".
        return str(self.topic_id)

    def submit_payment(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usd: float,
    ) -> PaymentDecision:
        approved = trust_score >= threshold
        tx_id = None

        if approved:
            receipt = (
                TransferTransaction()
                .add_hbar_transfer(self.operator_id, -DEMO_PAYMENT_TINYBARS)
                .add_hbar_transfer(self.agent_account_id, DEMO_PAYMENT_TINYBARS)
                .set_transaction_memo(f"AgentRanker payment: {target_agent_id}")
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )
            tx_id = str(receipt.transaction_id)

        reason = (
            f"trust_score {trust_score:.3f} >= threshold {threshold:.3f}"
            if approved
            else f"trust_score {trust_score:.3f} < threshold {threshold:.3f}"
        )

        decision = PaymentDecision(
            requester_id=requester_id,
            target_agent_id=target_agent_id,
            trust_score=trust_score,
            threshold=threshold,
            approved=approved,
            amount_usd=amount_usd,
            tx_id=tx_id,
            hcs_message_id=None,  # filled in below
            reason=reason,
        )

        # Always log the decision to HCS, approved or blocked.
        message = {
            "requester_id": requester_id,
            "target_agent_id": target_agent_id,
            "trust_score": trust_score,
            "threshold": threshold,
            "approved": approved,
            "amount_usd": amount_usd,
            "tx_id": tx_id,
            "reason": reason,
            "timestamp": int(time.time()),
        }
        decision.hcs_message_id = self.log_to_hcs(message)

        return decision

    def log_to_hcs(self, message: dict) -> str:
        receipt = (
            TopicMessageSubmitTransaction()
            .set_topic_id(self.topic_id)
            .set_message(json.dumps(message))
            .freeze_with(self.client)
            .sign(self.operator_key)
            .execute(self.client)
        )
        return f"{self.topic_id}/{receipt.topic_sequence_number}"
