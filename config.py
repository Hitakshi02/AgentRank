"""
Central config. Flip these flags to swap mock -> live per integration,
independently. Frontend never sees this file - it only talks to /api.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env in project root, if present

USE_LIVE_HEDERA   = os.environ.get("USE_LIVE_HEDERA",   "false").lower() == "true"
USE_LIVE_BIGQUERY = os.environ.get("USE_LIVE_BIGQUERY", "false").lower() == "true"
USE_LIVE_RAGAS    = os.environ.get("USE_LIVE_RAGAS",    "false").lower() == "true"
USE_LIVE_X402     = os.environ.get("USE_LIVE_X402",     "false").lower() == "true"

# Trust gate threshold (0-1 scale) used by the payment flow tab.
TRUST_THRESHOLD = float(os.environ.get("TRUST_THRESHOLD", "0.5"))

# Flat fee charged per query in the demo payment flow.
QUERY_FEE_USD = float(os.environ.get("QUERY_FEE_USD", "0.01"))


def get_hedera_client():
    if USE_LIVE_HEDERA:
        from integrations.hedera.live import LiveHederaClient
        return LiveHederaClient()
    from integrations.hedera.mock import MockHederaClient
    return MockHederaClient()


def get_bigquery_client():
    if USE_LIVE_BIGQUERY:
        from integrations.bigquery.live import LiveBigQueryClient
        return LiveBigQueryClient()
    from integrations.bigquery.mock import MockBigQueryClient
    return MockBigQueryClient()


def get_ragas_client():
    if USE_LIVE_RAGAS:
        from integrations.ragas.live import LiveRagasClient
        return LiveRagasClient()
    from integrations.ragas.mock import MockRagasClient
    return MockRagasClient()


def get_x402_client():
    if USE_LIVE_X402:
        from integrations.x402.live import LiveX402Client
        return LiveX402Client()
    from integrations.x402.mock import MockX402Client
    return MockX402Client()


