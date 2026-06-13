"""
Mock x402 implementation.
Returns realistic-shaped responses instantly — no Hedera account, no network calls.
Shapes its responses identically to live.py.
"""

import time
import random
from integrations.x402.base import X402Client

# Fixed recipient/amounts for mock — mirrors what live.py would use.
MOCK_RECIPIENT    = "0.0.9219095"   # matches HEDERA_AGENT_ACCOUNT_ID in .env
MOCK_TINYBARS     = 100_000         # 0.001 HBAR
MOCK_TOPIC        = "0.0.9219360"   # matches HEDERA_HCS_TOPIC_ID


def _fake_tx_id() -> str:
    account = random.randint(100000, 999999)
    seconds = int(time.time())
    nanos   = random.randint(0, 999_999_999)
    return f"0.0.{account}@{seconds}.{nanos:09d}"


class MockX402Client(X402Client):

    def get_payment_requirements(self, resource_id: str) -> dict:
        return {
            "version":  "x402/1",
            "resource": resource_id,
            "schemes": [{
                "scheme":          "hedera-testnet",
                "network":         "testnet",
                "recipient":       MOCK_RECIPIENT,
                "amount_tinybars": MOCK_TINYBARS,
                "memo_prefix":     f"x402:{resource_id}:",
                "description":     f"Pay-per-request: {resource_id} (0.001 HBAR)",
            }],
        }

    def submit_x402_payment(self, requirements: dict, requester_id: str) -> dict:
        scheme = requirements["schemes"][0]
        nonce  = str(int(time.time()))
        return {
            "scheme":          scheme["scheme"],
            "tx_id":           _fake_tx_id(),
            "memo":            f"{scheme['memo_prefix']}{nonce}",
            "amount_tinybars": scheme["amount_tinybars"],
            "requester_id":    requester_id,
            "timestamp":       int(time.time()),
        }

    def verify_x402_payment(self, payment_proof: dict, requirements: dict) -> tuple:
        return (True, "mock: payment accepted without on-chain verification")
