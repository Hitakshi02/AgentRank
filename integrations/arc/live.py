"""
Live Arc integration.
Executes a real ERC-20 USDC transfer on Arc testnet via web3.py.

Arc testnet:
  Chain ID : 5042002
  RPC      : https://rpc.testnet.arc.network
  USDC     : 0x3600000000000000000000000000000000000000
             (also the native gas token — gas is paid in USDC)

Required .env vars:
  ARC_OPERATOR_KEY     — private key of the sender account (0x-prefixed)
  ARC_AGENT_ADDRESS    — recipient address for payments (0x-prefixed)
  ARC_RPC_URL          — (optional) override default RPC

Faucet:
  https://faucet.circle.com/ → select "Arc Testnet" → 20 test USDC / 2h
"""

import os
from typing import Optional

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from integrations.arc.base import ArcClient
from core.models import PaymentDecision

ARC_CHAIN_ID      = 5042002
ARC_RPC_DEFAULT   = "https://rpc.testnet.arc.network"
USDC_ADDRESS      = Web3.to_checksum_address("0x3600000000000000000000000000000000000000")
USDC_DECIMALS     = 6

# Minimal ERC-20 ABI — only what we need
_USDC_ABI = [
    {
        "name": "transfer",
        "type": "function",
        "inputs": [
            {"name": "_to",    "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "name": "balanceOf",
        "type": "function",
        "inputs": [{"name": "_owner", "type": "address"}],
        "outputs": [{"name": "balance", "type": "uint256"}],
        "stateMutability": "view",
    },
]

# Demo nanopayment amount in USDC (adjustable via env)
DEMO_USDC_AMOUNT = float(os.environ.get("ARC_DEMO_USDC", "0.01"))


def _to_usdc_units(amount: float) -> int:
    return int(amount * 10 ** USDC_DECIMALS)


def _from_usdc_units(units: int) -> float:
    return units / 10 ** USDC_DECIMALS


class LiveArcClient(ArcClient):

    def __init__(self):
        rpc_url = os.environ.get("ARC_RPC_URL", ARC_RPC_DEFAULT)
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        # Arc is a PoA-style chain; inject middleware to handle extraData
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        raw_key = os.environ["ARC_OPERATOR_KEY"]
        self.account = self.w3.eth.account.from_key(raw_key)
        self.operator_address = self.account.address

        self.agent_address = Web3.to_checksum_address(
            os.environ["ARC_AGENT_ADDRESS"]
        )
        self.usdc = self.w3.eth.contract(address=USDC_ADDRESS, abi=_USDC_ABI)

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
        tx_id    = None

        recipient = Web3.to_checksum_address(
            recipient_address or self.agent_address
        )

        if approved:
            units = _to_usdc_units(amount_usdc)
            nonce = self.w3.eth.get_transaction_count(self.operator_address)

            tx = self.usdc.functions.transfer(recipient, units).build_transaction({
                "chainId":  ARC_CHAIN_ID,
                "from":     self.operator_address,
                "nonce":    nonce,
                "gas":      120_000,
                "gasPrice": self.w3.eth.gas_price,
            })
            signed  = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            tx_id   = "0x" + receipt["transactionHash"].hex().removeprefix("0x")

        reason = (
            f"trust_score {trust_score:.3f} >= threshold {threshold:.3f} — "
            f"${amount_usdc:.4f} USDC transferred on Arc testnet (tx: {tx_id})"
            if approved
            else f"trust_score {trust_score:.3f} < threshold {threshold:.3f} — payment blocked"
        )

        return PaymentDecision(
            requester_id=requester_id,
            target_agent_id=target_agent_id,
            trust_score=trust_score,
            threshold=threshold,
            approved=approved,
            amount_usd=amount_usdc,
            usdc_amount=amount_usdc,
            tx_id=tx_id,
            hcs_message_id=None,
            reason=reason,
            rail="arc",
        )

    def get_usdc_balance(self, address: str) -> float:
        addr  = Web3.to_checksum_address(address)
        units = self.usdc.functions.balanceOf(addr).call()
        return _from_usdc_units(units)
