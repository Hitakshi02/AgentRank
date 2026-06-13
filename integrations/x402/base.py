"""
Abstract interface for the x402 pay-per-request protocol.

The x402 standard (https://www.x402.org/) defines a machine-readable
HTTP 402 Payment Required flow:

  1. Client requests a protected resource.
  2. Server responds HTTP 402 with payment requirements (amount, recipient,
     network, memo scheme).
  3. Client creates an on-chain payment matching those requirements.
  4. Client retries the request, attaching the payment proof.
  5. Server verifies the payment on-chain and grants access.

This interface abstracts steps 2–5 so mock.py and live.py can be swapped
independently of the rest of the system.
"""

from abc import ABC, abstractmethod


class X402Client(ABC):

    @abstractmethod
    def get_payment_requirements(self, resource_id: str) -> dict:
        """
        Return the x402 payment requirements for a protected resource.

        Shape (mirrors the x402 spec JSON body returned in a 402 response):
        {
            "version": "x402/1",
            "resource": "<resource_id>",
            "schemes": [{
                "scheme":           "hedera-testnet",
                "network":          "testnet",
                "recipient":        "<Hedera account id>",
                "amount_tinybars":  <int>,
                "memo_prefix":      "x402:<resource_id>:",
                "description":      "<human-readable>",
            }]
        }
        """
        ...

    @abstractmethod
    def submit_x402_payment(self, requirements: dict, requester_id: str) -> dict:
        """
        Create an on-chain payment that satisfies the given requirements.

        Returns a payment proof:
        {
            "scheme":          "hedera-testnet",
            "tx_id":           "<Hedera transaction id>",
            "memo":            "x402:<resource_id>:<nonce>",
            "amount_tinybars": <int>,
            "requester_id":    "<str>",
            "timestamp":       <unix epoch seconds>,
        }
        """
        ...

    @abstractmethod
    def verify_x402_payment(self, payment_proof: dict, requirements: dict) -> tuple:
        """
        Verify that a payment proof satisfies the requirements.

        Returns (verified: bool, reason: str).
        In live.py this queries the Hedera mirror node REST API.
        In mock.py this always returns (True, "mock verified").
        """
        ...
