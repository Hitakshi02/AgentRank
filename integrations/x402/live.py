"""
Live x402 implementation on Hedera testnet.

Payment flow:
  1. get_payment_requirements() — returns the 402 JSON payload: amount, recipient, memo scheme.
  2. submit_x402_payment()      — creates a real HBAR TransferTransaction with the
                                   x402 memo pattern and submits it to Hedera testnet.
  3. verify_x402_payment()      — queries the Hedera testnet mirror node REST API to
                                   confirm the transaction: amount ✓, recipient ✓, memo ✓,
                                   recency ✓ (within 120 s), result = SUCCESS.

Requires .env:
  HEDERA_OPERATOR_ID, HEDERA_OPERATOR_KEY,
  HEDERA_AGENT_ACCOUNT_ID, HEDERA_HCS_TOPIC_ID

Mirror node used: https://testnet.mirrornode.hedera.com (free, no API key).
"""

import base64
import os
import time

import requests as http

from hiero_sdk_python import (
    AccountId,
    Client,
    Hbar,
    Network,
    PrivateKey,
    TopicId,
    TopicMessageSubmitTransaction,
    TransferTransaction,
)

from integrations.x402.base import X402Client

X402_FEE_TINYBARS    = 100_000   # 0.001 HBAR — the pay-per-request fee
PAYMENT_TTL_SECONDS  = 120       # reject proofs older than 2 min
MIRROR_NODE_BASE     = "https://testnet.mirrornode.hedera.com/api/v1"


def _tx_id_to_mirror(tx_id: str) -> str:
    """
    Convert Hedera SDK tx id  "0.0.9185886@1781376125.39472103"
    to mirror node path param "0.0.9185886-1781376125-039472103".
    The account id keeps its dots; only the @ and the timestamp's
    dot become dashes, and nanoseconds are zero-padded to 9 digits.
    """
    account, _, stamp = tx_id.partition("@")
    seconds, _, nanos = stamp.partition(".")
    nanos = nanos.zfill(9)  # mirror node requires 9-digit nanoseconds
    return f"{account}-{seconds}-{nanos}"


def _get_client() -> Client:
    operator_id  = AccountId.from_string(os.environ["HEDERA_OPERATOR_ID"])
    operator_key = PrivateKey.from_string(os.environ["HEDERA_OPERATOR_KEY"])
    client = Client(Network(network="testnet"))
    client.set_operator(operator_id, operator_key)
    return client


class LiveX402Client(X402Client):

    def __init__(self):
        self.client       = _get_client()
        self.operator_id  = AccountId.from_string(os.environ["HEDERA_OPERATOR_ID"])
        self.operator_key = PrivateKey.from_string(os.environ["HEDERA_OPERATOR_KEY"])
        self.recipient_id = AccountId.from_string(os.environ["HEDERA_AGENT_ACCOUNT_ID"])
        self.topic_id     = TopicId.from_string(os.environ["HEDERA_HCS_TOPIC_ID"])

    # ------------------------------------------------------------------
    def get_payment_requirements(self, resource_id: str) -> dict:
        return {
            "version":  "x402/1",
            "resource": resource_id,
            "schemes": [{
                "scheme":          "hedera-testnet",
                "network":         "testnet",
                "recipient":       str(self.recipient_id),
                "amount_tinybars": X402_FEE_TINYBARS,
                "memo_prefix":     f"x402:{resource_id}:",
                "description":     (
                    f"Pay-per-request: {resource_id} "
                    f"({X402_FEE_TINYBARS / 1e8:.5f} HBAR on Hedera testnet)"
                ),
            }],
        }

    # ------------------------------------------------------------------
    def submit_x402_payment(self, requirements: dict, requester_id: str) -> dict:
        scheme = requirements["schemes"][0]
        nonce  = str(int(time.time() * 1000))   # millisecond nonce for uniqueness
        memo   = f"{scheme['memo_prefix']}{nonce}"

        receipt = (
            TransferTransaction()
            .add_hbar_transfer(self.operator_id,  -scheme["amount_tinybars"])
            .add_hbar_transfer(self.recipient_id,  scheme["amount_tinybars"])
            .set_transaction_memo(memo)
            .freeze_with(self.client)
            .sign(self.operator_key)
            .execute(self.client)
        )
        tx_id = str(receipt.transaction_id)

        # Log to HCS so the payment is auditable alongside trust-gate decisions.
        self._log_to_hcs({
            "type":          "x402_payment",
            "resource":      requirements["resource"],
            "tx_id":         tx_id,
            "amount_tinybars": scheme["amount_tinybars"],
            "requester_id":  requester_id,
            "memo":          memo,
        })

        return {
            "scheme":          scheme["scheme"],
            "tx_id":           tx_id,
            "memo":            memo,
            "amount_tinybars": scheme["amount_tinybars"],
            "requester_id":    requester_id,
            "timestamp":       int(time.time()),
        }

    # ------------------------------------------------------------------
    def verify_x402_payment(self, payment_proof: dict, requirements: dict) -> tuple:
        tx_id     = payment_proof.get("tx_id", "")
        expected_memo_prefix = requirements["schemes"][0]["memo_prefix"]
        expected_recipient   = requirements["schemes"][0]["recipient"]
        expected_amount      = requirements["schemes"][0]["amount_tinybars"]

        if not tx_id:
            return (False, "no tx_id in payment proof")

        # Age check — reject stale proofs
        proof_ts = payment_proof.get("timestamp", 0)
        if time.time() - proof_ts > PAYMENT_TTL_SECONDS:
            return (False, f"payment proof expired (>{PAYMENT_TTL_SECONDS}s old)")

        # Query Hedera testnet mirror node, retrying while the fresh tx indexes
        mirror_id = _tx_id_to_mirror(tx_id)
        resp = None
        for attempt in range(5):
            try:
                resp = http.get(
                    f"{MIRROR_NODE_BASE}/transactions/{mirror_id}",
                    timeout=10,
                )
            except Exception as exc:
                return (False, f"mirror node unreachable: {exc}")
            if resp.status_code == 200:
                break
            # 404/400 = not indexed yet; wait and retry
            time.sleep(2)

        if resp is None or resp.status_code != 200:
            code = resp.status_code if resp is not None else "no response"
            return (False, f"mirror node returned HTTP {code} after retries")

        body = resp.json()
        txs  = body.get("transactions", [body])   # single tx or list
        tx   = txs[0] if txs else {}

        # Check result
        if tx.get("result") != "SUCCESS":
            return (False, f"transaction result: {tx.get('result', 'unknown')}")

        # Check memo (mirror node returns memo_base64)
        memo_b64  = tx.get("memo_base64", "")
        try:
            memo_actual = base64.b64decode(memo_b64).decode("utf-8", errors="replace")
        except Exception:
            memo_actual = ""

        if not memo_actual.startswith(expected_memo_prefix):
            return (False, f"memo mismatch: got '{memo_actual}', expected prefix '{expected_memo_prefix}'")

        # Check recipient transfer
        transfers = tx.get("transfers", [])
        paid_to_recipient = any(
            t.get("account") == expected_recipient and t.get("amount", 0) >= expected_amount
            for t in transfers
        )
        if not paid_to_recipient:
            return (
                False,
                f"required transfer of {expected_amount} tinybars to {expected_recipient} not found",
            )

        return (True, f"verified on Hedera testnet mirror node (tx {tx_id})")

    # ------------------------------------------------------------------
    def _log_to_hcs(self, message: dict) -> None:
        import json
        try:
            (
                TopicMessageSubmitTransaction()
                .set_topic_id(self.topic_id)
                .set_message(json.dumps(message))
                .freeze_with(self.client)
                .sign(self.operator_key)
                .execute(self.client)
            )
        except Exception:
            pass   # HCS logging is best-effort; don't fail the payment