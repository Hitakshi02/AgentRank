"""
One-time setup script: creates the HCS topic used for the
AgentRanker payment audit trail.

Run once:
    python3 scripts/setup_hedera.py

Copy the printed topic ID into your .env as HEDERA_HCS_TOPIC_ID,
then you're ready to set USE_LIVE_HEDERA=true.
"""

import os
from dotenv import load_dotenv
from hiero_sdk_python import Client, Network, AccountId, PrivateKey, TopicCreateTransaction

load_dotenv()


def main():
    operator_id = AccountId.from_string(os.environ["HEDERA_OPERATOR_ID"])
    operator_key = PrivateKey.from_string(os.environ["HEDERA_OPERATOR_KEY"])

    client = Client(Network(network="testnet"))
    client.set_operator(operator_id, operator_key)

    print("Creating HCS topic for AgentRanker audit trail...")

    receipt = (
        TopicCreateTransaction()
        .set_memo("AgentRanker payment audit trail")
        .freeze_with(client)
        .sign(operator_key)
        .execute(client)
    )

    topic_id = receipt.topic_id
    print(f"\nTopic created: {topic_id}")
    print(f"View on HashScan: https://hashscan.io/testnet/topic/{topic_id}")
    print(f"\nAdd this to your .env:\nHEDERA_HCS_TOPIC_ID={topic_id}")


if __name__ == "__main__":
    main()
