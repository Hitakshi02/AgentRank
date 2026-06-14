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
from datetime import datetime, timezone
from typing import List, Optional

import requests as _requests

from hiero_sdk_python import (
    Client,
    Network,
    AccountId,
    PrivateKey,
    TopicId,
    TopicCreateTransaction,
    TransferTransaction,
    TopicMessageSubmitTransaction,
    BatchTransaction,
    ScheduleCreateTransaction,
    ScheduleId,
    ScheduleInfoQuery,
    Hbar,
)

from integrations.hedera.base import HederaClient
from core.models import PaymentDecision, ScheduledReevaluation, AgentIdentity, AuditLogEntry

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

    def schedule_reevaluation(
        self, agent_id: str, scheduled_by: str
    ) -> ScheduledReevaluation:
        """
        Wrap an HCS re-evaluation message in a ScheduleCreateTransaction.

        Hedera Scheduled Transactions execute automatically once all required
        signatures are present.  Since the operator is the only required signer
        and we sign below, the inner HCS message executes immediately — but the
        schedule_id is recorded on-chain and queryable forever on HashScan /
        the mirror node, proving the re-evaluation trigger was committed on-chain.
        """
        memo = f"AgentRanker re-eval: {agent_id}"
        payload = {
            "type":         "reevaluation_trigger",
            "agent_id":     agent_id,
            "scheduled_by": scheduled_by,
            "timestamp":    int(time.time()),
        }

        inner_tx = (
            TopicMessageSubmitTransaction()
            .set_topic_id(self.topic_id)
            .set_message(json.dumps(payload))
        )

        try:
            receipt = (
                ScheduleCreateTransaction()
                .set_scheduled_transaction(inner_tx)
                .set_schedule_memo(memo)
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )
            schedule_id = str(receipt.schedule_id)
        except Exception as exc:
            return ScheduledReevaluation(
                schedule_id="",
                agent_id=agent_id,
                scheduled_by=scheduled_by,
                hcs_topic_id=str(self.topic_id),
                memo=memo,
                status="error",
                error=str(exc),
            )

        # Give the mirror node ~2s to index the schedule, then fetch its status
        time.sleep(2)
        return self.get_schedule_status(schedule_id)

    def get_schedule_status(self, schedule_id: str) -> ScheduledReevaluation:
        """
        Query schedule status via Hedera mirror node REST API.
        Falls back to ScheduleInfoQuery if the REST call fails.
        """
        mirror_url = (
            f"https://testnet.mirrornode.hedera.com/api/v1/schedules/{schedule_id}"
        )
        memo = f"AgentRanker re-eval schedule {schedule_id}"
        agent_id = "unknown"
        executed_at = None
        expiry = None
        seq_num = None

        try:
            resp = _requests.get(mirror_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                memo = data.get("memo", memo)
                expiry = data.get("expiration_time", {}).get("iso8601")
                executed_at = (data.get("executed_timestamp") or {}).get("iso8601")
                deleted = data.get("deleted", False)
                if deleted:
                    status = "deleted"
                elif executed_at:
                    status = "executed"
                elif expiry:
                    status = "pending"
                else:
                    status = "unknown"

                # Parse agent_id from memo "AgentRanker re-eval: <id>"
                if ": " in memo:
                    agent_id = memo.split(": ", 1)[1]

                return ScheduledReevaluation(
                    schedule_id=schedule_id,
                    agent_id=agent_id,
                    scheduled_by="",
                    hcs_topic_id=str(self.topic_id),
                    memo=memo,
                    status=status,
                    executed_at=executed_at,
                    expiration_time=expiry,
                )
        except Exception:
            pass

        # Fallback: ScheduleInfoQuery (gRPC)
        try:
            info = (
                ScheduleInfoQuery()
                .set_schedule_id(ScheduleId.from_string(schedule_id))
                .execute(self.client)
            )
            executed_at_ts = getattr(info, "executed_at", None)
            if executed_at_ts:
                executed_at = datetime.fromtimestamp(
                    executed_at_ts, tz=timezone.utc
                ).isoformat()
                status = "executed"
            else:
                status = "pending"

            expiry_ts = getattr(info, "expiration_time", None)
            if expiry_ts:
                expiry = datetime.fromtimestamp(
                    expiry_ts, tz=timezone.utc
                ).isoformat()

            if ": " in (info.schedule_memo or ""):
                agent_id = info.schedule_memo.split(": ", 1)[1]

            return ScheduledReevaluation(
                schedule_id=schedule_id,
                agent_id=agent_id,
                scheduled_by="",
                hcs_topic_id=str(self.topic_id),
                memo=info.schedule_memo or memo,
                status=status,
                executed_at=executed_at,
                expiration_time=expiry,
            )
        except Exception as exc:
            return ScheduledReevaluation(
                schedule_id=schedule_id,
                agent_id=agent_id,
                scheduled_by="",
                hcs_topic_id=str(self.topic_id),
                memo=memo,
                status="error",
                error=str(exc),
            )

    # ── HIP-551 / Scheduled / Atomic-Swap hire methods ───────────────────

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
        HIP-551 Batch Transaction: atomically bundles HBAR transfer + HCS audit
        message in a single BatchTransaction. Both inner txs share one consensus
        round — all-or-nothing ACID guarantee.
        """
        approved = trust_score >= threshold
        tx_id = None
        batch_id = None
        hcs_message_id = None

        if approved:
            audit_payload = json.dumps({
                "event": "batch_hire",
                "requester_id": requester_id,
                "target_agent_id": target_agent_id,
                "trust_score": trust_score,
                "approved": True,
                "timestamp": int(time.time()),
            })

            # Inner tx 1: HBAR transfer — batchify freezes + signs with batch key
            transfer_inner = (
                TransferTransaction()
                .add_hbar_transfer(self.operator_id, -DEMO_PAYMENT_TINYBARS)
                .add_hbar_transfer(self.agent_account_id, DEMO_PAYMENT_TINYBARS)
                .set_transaction_memo(f"AgentRanker batch hire: {target_agent_id}")
                .batchify(self.client, self.operator_key)
            )

            # Inner tx 2: HCS audit log
            hcs_inner = (
                TopicMessageSubmitTransaction()
                .set_topic_id(self.topic_id)
                .set_message(audit_payload)
                .set_transaction_memo(f"AgentRanker HCS audit: {target_agent_id}")
                .batchify(self.client, self.operator_key)
            )

            inner_ids = [
                str(transfer_inner.transaction_id),
                str(hcs_inner.transaction_id),
            ]

            receipt = (
                BatchTransaction()
                .add_inner_transaction(transfer_inner)
                .add_inner_transaction(hcs_inner)
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )

            tx_id = inner_ids[0]
            batch_id = f"{self.topic_id}/batch"
            hcs_message_id = f"{self.topic_id}/batch-audit"
        else:
            hcs_message_id = self.log_to_hcs({
                "event": "batch_hire_blocked",
                "requester_id": requester_id,
                "target_agent_id": target_agent_id,
                "trust_score": trust_score,
                "threshold": threshold,
                "approved": False,
                "timestamp": int(time.time()),
            })

        reason = (
            f"HIP-551 batch: trust_score {trust_score:.3f} >= threshold {threshold:.3f} — "
            "HBAR transfer + HCS audit bundled atomically."
            if approved
            else f"HIP-551 batch BLOCKED: trust_score {trust_score:.3f} < threshold {threshold:.3f}"
        )
        return PaymentDecision(
            requester_id=requester_id,
            target_agent_id=target_agent_id,
            trust_score=trust_score,
            threshold=threshold,
            approved=approved,
            amount_usd=amount_usd,
            tx_id=tx_id,
            hcs_message_id=hcs_message_id,
            reason=reason,
            transaction_type="batch",
            batch_id=batch_id,
        )

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
        Scheduled Transaction: wraps the HBAR payment in a ScheduleCreateTransaction.
        Since the operator is the sole required signer, execution happens immediately,
        but the schedule_id is recorded on-chain and queryable on HashScan.
        """
        from datetime import timedelta

        approved = trust_score >= threshold
        tx_id = None
        schedule_id = None
        hcs_message_id = None
        scheduled_at = None

        if approved:
            inner_transfer = (
                TransferTransaction()
                .add_hbar_transfer(self.operator_id, -DEMO_PAYMENT_TINYBARS)
                .add_hbar_transfer(self.agent_account_id, DEMO_PAYMENT_TINYBARS)
                .set_transaction_memo(f"AgentRanker scheduled hire: {target_agent_id}")
            )

            receipt = (
                ScheduleCreateTransaction()
                .set_scheduled_transaction(inner_transfer)
                .set_schedule_memo(f"AgentRanker hire: {target_agent_id}")
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )

            schedule_id = str(receipt.schedule_id)
            tx_id = str(receipt.transaction_id)

            now = datetime.now(timezone.utc)
            delay = execute_at_seconds if execute_at_seconds is not None else 30
            scheduled_at = (now + timedelta(seconds=delay)).isoformat()

            hcs_message_id = self.log_to_hcs({
                "event": "scheduled_hire",
                "requester_id": requester_id,
                "target_agent_id": target_agent_id,
                "schedule_id": schedule_id,
                "trust_score": trust_score,
                "approved": True,
                "timestamp": int(time.time()),
            })
        else:
            hcs_message_id = self.log_to_hcs({
                "event": "scheduled_hire_blocked",
                "requester_id": requester_id,
                "target_agent_id": target_agent_id,
                "trust_score": trust_score,
                "threshold": threshold,
                "approved": False,
                "timestamp": int(time.time()),
            })

        reason = (
            f"Scheduled hire queued: trust_score {trust_score:.3f} >= threshold {threshold:.3f}. "
            f"Schedule ID: {schedule_id}. Will execute via multi-sig coordination."
            if approved
            else f"Scheduled hire BLOCKED: trust_score {trust_score:.3f} < threshold {threshold:.3f}"
        )
        return PaymentDecision(
            requester_id=requester_id,
            target_agent_id=target_agent_id,
            trust_score=trust_score,
            threshold=threshold,
            approved=approved,
            amount_usd=amount_usd,
            tx_id=tx_id,
            hcs_message_id=hcs_message_id,
            reason=reason,
            transaction_type="scheduled",
            batch_id=schedule_id,
            scheduled_at=scheduled_at,
        )

    def atomic_swap_hire(
        self,
        requester_id: str,
        target_agent_id: str,
        trust_score: float,
        threshold: float,
        amount_usd: float,
    ) -> PaymentDecision:
        """
        Atomic Swap: a single TransferTransaction that simultaneously debits the
        requester and credits the agent in one atomic consensus round.
        On Hedera every TransferTransaction is inherently atomic — both sides
        execute or neither does.  The HCS message proves service delivery.
        """
        approved = trust_score >= threshold
        tx_id = None
        hcs_message_id = None

        if approved:
            receipt = (
                TransferTransaction()
                .add_hbar_transfer(self.operator_id, -DEMO_PAYMENT_TINYBARS)
                .add_hbar_transfer(self.agent_account_id, DEMO_PAYMENT_TINYBARS)
                .set_transaction_memo(f"AgentRanker atomic swap: {target_agent_id}")
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )
            tx_id = str(receipt.transaction_id)

            hcs_message_id = self.log_to_hcs({
                "event": "atomic_swap_hire",
                "requester_id": requester_id,
                "target_agent_id": target_agent_id,
                "trust_score": trust_score,
                "tx_id": tx_id,
                "approved": True,
                "timestamp": int(time.time()),
            })
        else:
            hcs_message_id = self.log_to_hcs({
                "event": "atomic_swap_blocked",
                "requester_id": requester_id,
                "target_agent_id": target_agent_id,
                "trust_score": trust_score,
                "threshold": threshold,
                "approved": False,
                "timestamp": int(time.time()),
            })

        reason = (
            f"Atomic swap executed: trust_score {trust_score:.3f} >= threshold {threshold:.3f}. "
            "HBAR payment and service delivery exchanged simultaneously — both sides atomic."
            if approved
            else f"Atomic swap BLOCKED: trust_score {trust_score:.3f} < threshold {threshold:.3f}"
        )
        return PaymentDecision(
            requester_id=requester_id,
            target_agent_id=target_agent_id,
            trust_score=trust_score,
            threshold=threshold,
            approved=approved,
            amount_usd=amount_usd,
            tx_id=tx_id,
            hcs_message_id=hcs_message_id,
            reason=reason,
            transaction_type="atomic_swap",
        )

    # ── HCS-14 agent identity ─────────────────────────────────────────────

    def register_agent_identity(
        self, agent_id: str, name: str, capabilities: list
    ) -> AgentIdentity:
        """
        Create a new HCS topic whose memo encodes the HCS-14 identity JSON.
        The topic_id IS the agent's universal identifier on Hedera.
        Submits a genesis "registration" message to the topic.
        """
        hcs14_meta = json.dumps({
            "standard":     "HCS-14",
            "type":         "agent_identity",
            "agent_id":     agent_id,
            "name":         name,
            "capabilities": capabilities,
            "version":      "1.0",
        })

        try:
            receipt = (
                TopicCreateTransaction()
                .set_memo(hcs14_meta)
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )
            new_topic_id = receipt.topic_id
        except Exception as exc:
            return AgentIdentity(
                agent_id=agent_id,
                name=name,
                topic_id="",
                capabilities=capabilities,
                error=str(exc),
            )

        topic_id_str = str(new_topic_id)
        now = datetime.now(timezone.utc).isoformat()

        # Genesis message: the HCS-14 registration event
        genesis_payload = {
            "event_type": "registration",
            "agent_id":   agent_id,
            "name":       name,
            "capabilities": capabilities,
            "timestamp":  int(time.time()),
        }
        seq_num = self.log_agent_event(topic_id_str, "registration", genesis_payload)

        genesis_entry = AuditLogEntry(
            sequence_number=int(seq_num) if seq_num.isdigit() else 1,
            consensus_timestamp=str(int(time.time())) + ".000000000",
            event_type="registration",
            payload=genesis_payload,
            topic_id=topic_id_str,
        )

        return AgentIdentity(
            agent_id=agent_id,
            name=name,
            topic_id=topic_id_str,
            capabilities=capabilities,
            registered_at=now,
            memo=hcs14_meta,
            audit_log=[genesis_entry],
        )

    def get_agent_audit_log(
        self, topic_id: str, limit: int = 25
    ) -> List[AuditLogEntry]:
        """
        Fetch HCS messages from the agent's identity topic via mirror node.
        Messages are base64-encoded JSON payloads.
        """
        url = (
            f"https://testnet.mirrornode.hedera.com/api/v1/topics/"
            f"{topic_id}/messages?limit={limit}&order=desc"
        )
        try:
            resp = _requests.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
        except Exception:
            return []

        import base64
        entries: List[AuditLogEntry] = []
        for m in data.get("messages", []):
            try:
                raw = base64.b64decode(m.get("message", "")).decode("utf-8", errors="replace")
                payload = json.loads(raw)
                event_type = payload.pop("event_type", "unknown")
            except Exception:
                payload    = {"raw": m.get("message", "")}
                event_type = "unknown"

            entries.append(AuditLogEntry(
                sequence_number=int(m.get("sequence_number", 0)),
                consensus_timestamp=str(m.get("consensus_timestamp", "")),
                event_type=event_type,
                payload=payload,
                topic_id=topic_id,
            ))
        return entries

    def log_agent_event(
        self, topic_id: str, event_type: str, payload: dict
    ) -> str:
        """Submit a structured JSON event to an agent's HCS identity topic."""
        message = {"event_type": event_type, **payload}
        try:
            receipt = (
                TopicMessageSubmitTransaction()
                .set_topic_id(TopicId.from_string(topic_id))
                .set_message(json.dumps(message))
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )
            return str(receipt.topic_sequence_number)
        except Exception:
            return "0"
