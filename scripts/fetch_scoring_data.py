"""
One-time script to populate the scoring data fixtures from BigQuery.

Run this once before the demo to avoid ~$9 BigQuery transaction-table scans
on every scoring request.  After running, all demo sessions use the cached
fixtures at zero cost.

Usage:
    python scripts/fetch_scoring_data.py

Requires:
    - GOOGLE_CLOUD_PROJECT env var (or .env file)
    - Application Default Credentials:  gcloud auth application-default login
      OR GOOGLE_APPLICATION_CREDENTIALS pointing to a service account key

Output files:
    fixtures/feedback_cache.json      — all FeedbackGiven events with decoded scores
    fixtures/wallet_stats_cache.json  — wallet age + tx count for every giver
"""

import json
import os
import sys
from pathlib import Path

# Allow running from repo root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load .env if present
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from integrations.bigquery.live import LiveBigQueryClient


def main():
    print("Connecting to BigQuery...")
    bq = LiveBigQueryClient()

    # ── Step 1: Fetch all feedback events ────────────────────────────────
    print("Fetching FeedbackGiven events (all-time, ~50 MB scan)...")
    feedbacks = bq.get_feedback_for_scoring()
    print(f"  Got {len(feedbacks)} feedback events.")

    feedback_path = ROOT / "fixtures" / "feedback_cache.json"
    feedback_data = {
        "feedback_events": [
            {
                "agent_id":      f.agent_id,
                "giver_address": f.giver_address,
                "quality_score": f.quality_score,
                "vote_weight":   f.vote_weight,
                "timestamp":     f.timestamp,
            }
            for f in feedbacks
        ]
    }
    feedback_path.write_text(json.dumps(feedback_data, indent=2, default=str))
    print(f"  Saved to {feedback_path}")

    # ── Step 2: Fetch wallet stats for all givers ────────────────────────
    giver_addresses = list({f.giver_address for f in feedbacks})
    print(f"Fetching wallet stats for {len(giver_addresses)} unique giver addresses...")
    print("  (This scans crypto_ethereum.transactions — may cost ~$9 and take 1-2 min)")

    wallet_stats = bq.get_giver_wallet_stats(giver_addresses)
    print(f"  Got stats for {len(wallet_stats)} wallets.")

    wallet_path = ROOT / "fixtures" / "wallet_stats_cache.json"
    wallet_data = {
        "wallet_stats": {
            addr: {
                "wallet_age_days": stats.wallet_age_days,
                "tx_count":        stats.tx_count,
            }
            for addr, stats in wallet_stats.items()
        }
    }
    wallet_path.write_text(json.dumps(wallet_data, indent=2))
    print(f"  Saved to {wallet_path}")

    print("\nDone. Scoring data cached. Future demo runs cost $0.")


if __name__ == "__main__":
    main()
