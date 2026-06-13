"""
Mock Hedera implementation.
Returns instantly, no network calls, no testnet account needed.
Shapes its responses identically to live.py so the rest of the app
doesn't need to know which one is active.
"""

import json
import time
import random
from pathlib import Path
from integrations.hedera.base import HederaClient
from core.models import PaymentDecision

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures" / "agents.json"


def _load_agents():
    with open(FIXTURES_PATH) as f:
        return json.load(f)["agents"]


def _fake_tx_id() -> str:
    # Shaped like a real Hedera testnet tx id: 0.0.<account>@<seconds>.<nanos>
    account = random.randint(100000, 999999)
    seconds = int(time.time())
    nanos = random.randint(0, 999999999)
    return f"0.0.{account}@{seconds}.{nanos:09d}"


def _fake_hcs_message_id() -> str:
    topic = random.randint(6400000, 6499999)
    seq = random.randint(1, 9999)
    return f"0.0.{topic}/{seq}"


class MockHederaClient(HederaClient):

    def get_agent_identity(self, agent_id: str) -> str | None:
        agents = {a["agent_id"]: a for a in _load_agents()}
        agent = agents.get(agent_id)
        if agent is None:
            return None
        return agent.get("hedera_topic_id")

    def submit_payment(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usd: float,
    ) -> PaymentDecision:
        approved = trust_score >= threshold

        decision = PaymentDecision(
            requester_id=requester_id,
            target_agent_id=target_agent_id,
            trust_score=trust_score,
            threshold=threshold,
            approved=approved,
            amount_usd=amount_usd,
            tx_id=_fake_tx_id() if approved else None,
            hcs_message_id=_fake_hcs_message_id(),
            reason=(
                f"trust_score {trust_score:.3f} >= threshold {threshold:.3f}"
                if approved
                else f"trust_score {trust_score:.3f} < threshold {threshold:.3f}"
            ),
        )
        return decision

    def log_to_hcs(self, message: dict) -> str:
        return _fake_hcs_message_id()
