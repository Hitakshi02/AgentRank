"""
Mock Hedera implementation.
Returns instantly, no network calls, no testnet account needed.
Shapes its responses identically to live.py so the rest of the app
doesn't need to know which one is active.
"""

import json
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List
from integrations.hedera.base import HederaClient
from core.models import PaymentDecision, ScheduledReevaluation, AgentIdentity, AuditLogEntry

AUDIT_CACHE = Path(__file__).parent.parent.parent / "fixtures" / "audit_log_cache.json"

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

    def schedule_reevaluation(
        self, agent_id: str, scheduled_by: str
    ) -> ScheduledReevaluation:
        schedule_num = random.randint(6500000, 6599999)
        schedule_id  = f"0.0.{schedule_num}"
        topic_num    = random.randint(6400000, 6499999)
        topic_id     = f"0.0.{topic_num}"
        now = datetime.now(timezone.utc)
        expiry = (now + timedelta(hours=24)).isoformat()
        memo = f"AgentRanker re-eval: {agent_id}"
        return ScheduledReevaluation(
            schedule_id=schedule_id,
            agent_id=agent_id,
            scheduled_by=scheduled_by,
            hcs_topic_id=topic_id,
            memo=memo,
            status="executed",          # mock: executes immediately (operator is sole signer)
            executed_at=now.isoformat(),
            expiration_time=expiry,
            hcs_sequence_number=random.randint(1, 9999),
        )

    def register_agent_identity(
        self, agent_id: str, name: str, capabilities: list
    ) -> AgentIdentity:
        import json as _json
        topic_num = random.randint(6600000, 6699999)
        topic_id  = f"0.0.{topic_num}"
        now = datetime.now(timezone.utc).isoformat()
        memo = _json.dumps({
            "standard": "HCS-14",
            "type": "agent_identity",
            "agent_id": agent_id,
            "name": name,
            "capabilities": capabilities,
            "version": "1.0",
        })
        genesis = AuditLogEntry(
            sequence_number=1,
            consensus_timestamp=str(int(time.time())) + ".000000000",
            event_type="registration",
            payload={
                "standard": "HCS-14",
                "agent_id": agent_id,
                "name": name,
                "capabilities": capabilities,
            },
            topic_id=topic_id,
        )
        return AgentIdentity(
            agent_id=agent_id,
            name=name,
            topic_id=topic_id,
            capabilities=capabilities,
            registered_at=now,
            memo=memo,
            audit_log=[genesis],
        )

    def get_agent_audit_log(
        self, topic_id: str, limit: int = 25
    ) -> List[AuditLogEntry]:
        if not AUDIT_CACHE.exists():
            return []
        data = json.load(open(AUDIT_CACHE))
        topic_data = data.get("topics", {}).get(topic_id)
        if not topic_data:
            return []
        entries = []
        for m in topic_data.get("messages", [])[:limit]:
            entries.append(AuditLogEntry(
                sequence_number=m["sequence_number"],
                consensus_timestamp=m["consensus_timestamp"],
                event_type=m["event_type"],
                payload=m.get("payload", {}),
                topic_id=topic_id,
            ))
        return entries

    def log_agent_event(
        self, topic_id: str, event_type: str, payload: dict
    ) -> str:
        return str(random.randint(1, 9999))

    def get_schedule_status(self, schedule_id: str) -> ScheduledReevaluation:
        now = datetime.now(timezone.utc)
        return ScheduledReevaluation(
            schedule_id=schedule_id,
            agent_id="unknown",
            scheduled_by="unknown",
            hcs_topic_id="0.0.0",
            memo=f"AgentRanker re-eval (mock lookup: {schedule_id})",
            status="executed",
            executed_at=now.isoformat(),
        )
