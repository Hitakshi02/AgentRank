"""
Task 0: ERC-8004 Dataset Investigation
Queries bigquery-public-data.crypto_ethereum.logs for both ERC-8004 contracts
and answers all five pre-build questions before any feature work begins.

Run:
    python scripts/explore_dataset.py [--project YOUR_GCP_PROJECT]

Writes findings to docs/dataset_findings.md
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

IDENTITY_REGISTRY   = "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432"
REPUTATION_REGISTRY = "0x8004baa17c55a88189ae136b182e5fda19de9b63"

# Known keccak256 topic signatures (pre-computed)
KNOWN_TOPICS = {
    # ERC-721 / ERC-8004 IdentityRegistry
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
        "Transfer(address indexed from, address indexed to, uint256 indexed tokenId)",
    "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925":
        "Approval(address indexed owner, address indexed approved, uint256 indexed tokenId)",
    "0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31":
        "ApprovalForAll(address indexed owner, address indexed operator, bool approved)",
    # ERC-8004 specific events (keccak256 of the signatures)
    "0x6bb7ff708619ba0610cba295a58592e0451dee2622938c8755667688daf3529b":
        "URI(string value, uint256 indexed id)",
    # ReputationRegistry - FeedbackGiven variants
    # keccak256("FeedbackGiven(uint256,address,int256,uint8,string,bytes32)")
    "0x0d0c4b02000000000000000000000000000000000000000000000000000000":
        "PLACEHOLDER - will be replaced by real query",
}

# ERC-8004 ABI-derived keccak256 topic hashes (computed manually for reference)
# These are the LIKELY signatures - the real topics in BigQuery will tell us what's there
PROBABLE_FEEDBACK_SIGS = [
    "FeedbackGiven(uint256,address,int256,uint8,string,bytes32)",
    "FeedbackGiven(uint256,address,uint256,string)",
    "FeedbackSubmitted(uint256,address,int256,uint8)",
    "ReputationUpdated(uint256,int256)",
    "Feedback(uint256,address,int256)",
]


# ──────────────────────────────────────────────────────────────
# Q1: What event topic[0] signatures appear on each contract?
# ──────────────────────────────────────────────────────────────
Q1_IDENTITY_TOPICS = f"""
SELECT
  topics[SAFE_OFFSET(0)] AS topic0,
  COUNT(*) AS event_count,
  COUNT(DISTINCT DATE(block_timestamp)) AS active_days,
  MIN(block_timestamp) AS first_seen,
  MAX(block_timestamp) AS last_seen
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{IDENTITY_REGISTRY}'
  AND topics[SAFE_OFFSET(0)] IS NOT NULL
GROUP BY topic0
ORDER BY event_count DESC
"""

Q1_REPUTATION_TOPICS = f"""
SELECT
  topics[SAFE_OFFSET(0)] AS topic0,
  COUNT(*) AS event_count,
  COUNT(DISTINCT DATE(block_timestamp)) AS active_days,
  MIN(block_timestamp) AS first_seen,
  MAX(block_timestamp) AS last_seen
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{REPUTATION_REGISTRY}'
  AND topics[SAFE_OFFSET(0)] IS NOT NULL
GROUP BY topic0
ORDER BY event_count DESC
"""

# ──────────────────────────────────────────────────────────────
# Q1b: Inspect sample logs rows so we can understand topic/data layout
# ──────────────────────────────────────────────────────────────
Q1_SAMPLE_IDENTITY = f"""
SELECT
  block_timestamp,
  topics,
  data,
  transaction_hash
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{IDENTITY_REGISTRY}'
LIMIT 5
"""

Q1_SAMPLE_REPUTATION = f"""
SELECT
  block_timestamp,
  topics,
  data,
  transaction_hash
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{REPUTATION_REGISTRY}'
LIMIT 5
"""

# ──────────────────────────────────────────────────────────────
# Q2: Can we decode feedback VALUE from event data?
# Pull sample reputation events with raw data bytes
# ──────────────────────────────────────────────────────────────
Q2_REPUTATION_DATA_SAMPLE = f"""
SELECT
  block_timestamp,
  topics,
  data,
  LENGTH(data) AS data_bytes,
  transaction_hash
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{REPUTATION_REGISTRY}'
  AND data IS NOT NULL
  AND data != '0x'
  AND data != ''
LIMIT 20
"""

# Count events by data length to understand encoding
Q2_DATA_LENGTH_DISTRIBUTION = f"""
SELECT
  CASE
    WHEN data IS NULL OR data = '0x' OR data = '' THEN 'empty'
    WHEN LENGTH(data) <= 66 THEN '<=32bytes'
    WHEN LENGTH(data) <= 130 THEN '<=64bytes'
    WHEN LENGTH(data) <= 194 THEN '<=96bytes'
    WHEN LENGTH(data) <= 258 THEN '<=128bytes'
    ELSE '>128bytes'
  END AS data_size_bucket,
  COUNT(*) AS count
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{REPUTATION_REGISTRY}'
GROUP BY data_size_bucket
ORDER BY count DESC
"""

# ──────────────────────────────────────────────────────────────
# Q3: Agent metadata / domain signals (URI hints, registration data)
# ──────────────────────────────────────────────────────────────
Q3_IDENTITY_DATA_SAMPLE = f"""
SELECT
  block_timestamp,
  topics,
  data,
  LENGTH(data) AS data_bytes,
  transaction_hash
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{IDENTITY_REGISTRY}'
  AND data IS NOT NULL
  AND data != '0x'
  AND data != ''
LIMIT 20
"""

# Look for URI events specifically (ERC-1155/metadata pattern)
Q3_URI_EVENTS = f"""
SELECT
  topics[SAFE_OFFSET(0)] AS topic0,
  topics[SAFE_OFFSET(1)] AS topic1,
  data,
  transaction_hash,
  block_timestamp
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{IDENTITY_REGISTRY}'
  AND topics[SAFE_OFFSET(0)] = '0x6bb7ff708619ba0610cba295a58592e0451dee2622938c8755667688daf3529b'
LIMIT 10
"""

# ──────────────────────────────────────────────────────────────
# Q4: How many agents have BOTH identity AND feedback?
# ──────────────────────────────────────────────────────────────
ZERO_TOPIC = "0x0000000000000000000000000000000000000000000000000000000000000000"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

Q4_OVERLAP = f"""
WITH registered_agents AS (
  SELECT DISTINCT
    topics[SAFE_OFFSET(3)] AS agent_id_hex,
    LOWER(CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], -40))) AS owner_address
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{IDENTITY_REGISTRY}'
    AND topics[SAFE_OFFSET(0)] = '{TRANSFER_TOPIC}'
    AND topics[SAFE_OFFSET(1)] = '{ZERO_TOPIC}'
),
agents_with_feedback AS (
  SELECT DISTINCT
    topics[SAFE_OFFSET(1)] AS agent_id_hex
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{REPUTATION_REGISTRY}'
    AND topics[SAFE_OFFSET(1)] IS NOT NULL
)
SELECT
  COUNT(DISTINCT r.agent_id_hex) AS total_registered,
  COUNT(DISTINCT f.agent_id_hex) AS total_with_feedback,
  COUNT(DISTINCT CASE WHEN f.agent_id_hex IS NOT NULL THEN r.agent_id_hex END) AS both_identity_and_feedback,
  COUNT(DISTINCT CASE WHEN f.agent_id_hex IS NULL THEN r.agent_id_hex END) AS identity_only,
  COUNT(DISTINCT CASE WHEN r.agent_id_hex IS NULL THEN f.agent_id_hex END) AS feedback_without_identity
FROM registered_agents r
FULL OUTER JOIN agents_with_feedback f ON r.agent_id_hex = f.agent_id_hex
"""

# Also get the full set of unique agent IDs that have feedback
Q4_FEEDBACK_AGENT_COUNT = f"""
SELECT
  topics[SAFE_OFFSET(1)] AS agent_id_hex,
  COUNT(*) AS feedback_events,
  COUNT(DISTINCT topics[SAFE_OFFSET(2)]) AS distinct_givers_indexed
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{REPUTATION_REGISTRY}'
  AND topics[SAFE_OFFSET(1)] IS NOT NULL
GROUP BY agent_id_hex
ORDER BY feedback_events DESC
LIMIT 20
"""

# ──────────────────────────────────────────────────────────────
# Q5: Giver-address join feasibility + cost estimate
# Pull feedback events with giver address, join to tx data
# ──────────────────────────────────────────────────────────────

# First understand if giver address is in topics (indexed) or data (non-indexed)
Q5_TOPIC_LAYOUT = f"""
SELECT
  topics[SAFE_OFFSET(0)] AS topic0,
  topics[SAFE_OFFSET(1)] AS topic1,
  topics[SAFE_OFFSET(2)] AS topic2,
  topics[SAFE_OFFSET(3)] AS topic3,
  data,
  block_timestamp
FROM `bigquery-public-data.crypto_ethereum.logs`
WHERE address = '{REPUTATION_REGISTRY}'
LIMIT 10
"""

# Feasibility check: pull feedback events + giver address (topic[2] as candidate)
# then join to transactions to get wallet age and activity
# IMPORTANT: we use TABLESAMPLE and date-bound to estimate cost before full run
Q5_GIVER_JOIN_SAMPLE = f"""
WITH feedback_events AS (
  SELECT
    topics[SAFE_OFFSET(1)] AS agent_id_hex,
    topics[SAFE_OFFSET(2)] AS giver_topic,
    LOWER(CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], -40))) AS giver_address,
    block_timestamp AS feedback_time,
    transaction_hash
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{REPUTATION_REGISTRY}'
    AND topics[SAFE_OFFSET(2)] IS NOT NULL
  LIMIT 100
),
giver_stats AS (
  SELECT
    from_address,
    MIN(block_timestamp) AS first_tx,
    COUNT(*) AS tx_count,
    MAX(block_timestamp) AS last_tx
  FROM `bigquery-public-data.crypto_ethereum.transactions`
  WHERE from_address IN (SELECT giver_address FROM feedback_events)
    AND block_timestamp >= TIMESTAMP('2020-01-01')
  GROUP BY from_address
)
SELECT
  f.agent_id_hex,
  f.giver_address,
  f.feedback_time,
  g.first_tx,
  g.tx_count,
  g.last_tx,
  DATE_DIFF(DATE(f.feedback_time), DATE(g.first_tx), DAY) AS wallet_age_days
FROM feedback_events f
LEFT JOIN giver_stats g ON f.giver_address = g.from_address
ORDER BY f.feedback_time DESC
LIMIT 20
"""

# Estimate bytes scanned for the full join (dry run only - won't actually scan)
Q5_COST_ESTIMATE_QUERY = f"""
WITH feedback_givers AS (
  SELECT DISTINCT
    LOWER(CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], -40))) AS giver_address
  FROM `bigquery-public-data.crypto_ethereum.logs`
  WHERE address = '{REPUTATION_REGISTRY}'
    AND topics[SAFE_OFFSET(2)] IS NOT NULL
)
SELECT COUNT(*) AS distinct_givers
FROM feedback_givers
"""


def run_query(client, sql: str, description: str, dry_run: bool = False):
    """Execute a BigQuery query and return rows, or just estimate cost."""
    from google.cloud import bigquery as bq

    job_config = bq.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    try:
        job = client.query(sql, job_config=job_config)
        if dry_run:
            gb = job.total_bytes_processed / 1e9
            return {"dry_run": True, "gb_processed": round(gb, 4)}
        rows = list(job.result())
        return rows
    except Exception as e:
        return {"error": str(e)}


def decode_topic_as_address(topic_hex: str) -> str:
    """Extract address from a 32-byte topic (last 20 bytes)."""
    if not topic_hex or len(topic_hex) < 42:
        return topic_hex or ""
    return "0x" + topic_hex[-40:]


def decode_int256_from_data(data_hex: str, slot: int = 0) -> int:
    """Decode a 32-byte slot from ABI-encoded data as signed int256."""
    if not data_hex or data_hex in ("0x", ""):
        return 0
    clean = data_hex[2:] if data_hex.startswith("0x") else data_hex
    start = slot * 64
    chunk = clean[start:start + 64]
    if len(chunk) < 64:
        return 0
    val = int(chunk, 16)
    # Two's complement for negative int256
    if val >= 2**255:
        val -= 2**256
    return val


def decode_uint8_from_data(data_hex: str, slot: int = 1) -> int:
    """Decode a uint8 from a 32-byte ABI slot."""
    if not data_hex or data_hex in ("0x", ""):
        return 0
    clean = data_hex[2:] if data_hex.startswith("0x") else data_hex
    start = slot * 64
    chunk = clean[start:start + 64]
    if len(chunk) < 64:
        return 0
    return int(chunk, 16) & 0xFF


def format_rows(rows, max_rows: int = 10) -> str:
    """Format BigQuery row results for markdown output."""
    if isinstance(rows, dict):
        return f"```\n{json.dumps(rows, indent=2, default=str)}\n```"
    if not rows:
        return "_No rows returned._"
    lines = []
    for i, row in enumerate(rows[:max_rows]):
        d = dict(row)
        lines.append(f"  Row {i+1}: {json.dumps(d, default=str)}")
    if len(rows) > max_rows:
        lines.append(f"  ... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--output", default=str(ROOT / "docs" / "dataset_findings.md"))
    args = parser.parse_args()

    if not args.project:
        print("ERROR: set GOOGLE_CLOUD_PROJECT env var or pass --project", file=sys.stderr)
        sys.exit(1)

    from google.cloud import bigquery
    client = bigquery.Client(project=args.project)

    print("=== AgentRanker: ERC-8004 Dataset Investigation ===\n")
    findings = {}

    # ── Q1: Topic signatures on IdentityRegistry ──────────────────────────────
    print("[Q1a] Querying IdentityRegistry event topics...")
    id_topics = run_query(client, Q1_IDENTITY_TOPICS, "IdentityRegistry topics")
    findings["id_topics"] = id_topics

    print("[Q1b] Querying ReputationRegistry event topics...")
    rep_topics = run_query(client, Q1_REPUTATION_TOPICS, "ReputationRegistry topics")
    findings["rep_topics"] = rep_topics

    print("[Q1c] Sample IdentityRegistry rows (raw)...")
    id_sample = run_query(client, Q1_SAMPLE_IDENTITY, "IdentityRegistry sample")
    findings["id_sample"] = id_sample

    print("[Q1d] Sample ReputationRegistry rows (raw)...")
    rep_sample = run_query(client, Q1_SAMPLE_REPUTATION, "ReputationRegistry sample")
    findings["rep_sample"] = rep_sample

    # ── Q2: Feedback value decodability ──────────────────────────────────────
    print("[Q2a] Reputation data field samples...")
    rep_data = run_query(client, Q2_REPUTATION_DATA_SAMPLE, "Reputation data")
    findings["rep_data"] = rep_data

    print("[Q2b] Reputation data length distribution...")
    data_dist = run_query(client, Q2_DATA_LENGTH_DISTRIBUTION, "Data length dist")
    findings["data_dist"] = data_dist

    # Try to decode int256 value from sample rows
    decoded_values = []
    if isinstance(rep_data, list):
        for row in rep_data[:10]:
            d = dict(row)
            raw_data = d.get("data", "")
            topics = d.get("topics", [])
            if raw_data and raw_data not in ("0x", ""):
                val = decode_int256_from_data(raw_data, slot=0)
                decimals = decode_uint8_from_data(raw_data, slot=1)
                giver_from_topic2 = decode_topic_as_address(
                    topics[2] if len(topics) > 2 else ""
                )
                decoded_values.append({
                    "tx": d.get("transaction_hash", "")[:20],
                    "raw_data_len": len(raw_data),
                    "topic_count": len(topics),
                    "decoded_int256_slot0": val,
                    "decoded_uint8_slot1": decimals,
                    "giver_from_topic2": giver_from_topic2,
                    "ts": str(d.get("block_timestamp", "")),
                })
    findings["decoded_feedback"] = decoded_values

    # ── Q3: Agent metadata / domain ───────────────────────────────────────────
    print("[Q3a] IdentityRegistry non-empty data samples...")
    id_data = run_query(client, Q3_IDENTITY_DATA_SAMPLE, "Identity data")
    findings["id_data"] = id_data

    print("[Q3b] URI events on IdentityRegistry...")
    uri_events = run_query(client, Q3_URI_EVENTS, "URI events")
    findings["uri_events"] = uri_events

    # ── Q4: Overlap (identity + feedback) ────────────────────────────────────
    print("[Q4a] Identity-feedback overlap stats...")
    overlap = run_query(client, Q4_OVERLAP, "Overlap")
    findings["overlap"] = overlap

    print("[Q4b] Top agents by feedback count...")
    feedback_top = run_query(client, Q4_FEEDBACK_AGENT_COUNT, "Top feedback agents")
    findings["feedback_top"] = feedback_top

    # ── Q5: Giver join feasibility ────────────────────────────────────────────
    print("[Q5a] Topic layout sample...")
    topic_layout = run_query(client, Q5_TOPIC_LAYOUT, "Topic layout")
    findings["topic_layout"] = topic_layout

    print("[Q5b] Giver-wallet join sample (100 events → tx stats)...")
    giver_join = run_query(client, Q5_GIVER_JOIN_SAMPLE, "Giver join")
    findings["giver_join"] = giver_join

    print("[Q5c] Distinct giver count (for cost estimate)...")
    giver_count = run_query(client, Q5_COST_ESTIMATE_QUERY, "Giver count")
    findings["giver_count"] = giver_count

    # ── Dry-run cost estimates ─────────────────────────────────────────────────
    print("[Cost] Dry-run cost estimate for giver join (full)...")
    cost_est = run_query(
        client,
        Q5_GIVER_JOIN_SAMPLE.replace("LIMIT 100", "-- full").replace("LIMIT 20", ""),
        "Cost estimate",
        dry_run=True,
    )
    findings["cost_estimate"] = cost_est

    # ──────────────────────────────────────────────────────────────────────────
    # Write markdown findings
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Write] Saving findings to {args.output} ...")
    _write_findings(findings, args.output)
    print("Done.")


def _format_topic_table(rows) -> str:
    if isinstance(rows, dict):
        return f"**Error:** {rows.get('error', rows)}\n"
    if not rows:
        return "_No data._\n"
    lines = ["| topic0 | event_count | active_days | first_seen | last_seen | decoded |",
             "|--------|-------------|-------------|------------|-----------|---------|"]
    for row in rows:
        d = dict(row)
        t = d.get("topic0", "")
        decoded = KNOWN_TOPICS.get(t, "_unknown_")
        lines.append(
            f"| `{t[:20]}...` | {d.get('event_count')} | {d.get('active_days')} "
            f"| {str(d.get('first_seen',''))[:10]} | {str(d.get('last_seen',''))[:10]} | {decoded} |"
        )
    return "\n".join(lines) + "\n"


def _format_giver_join(rows) -> str:
    if isinstance(rows, dict):
        return f"**Error:** {rows.get('error', rows)}\n"
    if not rows:
        return "_No data._\n"
    lines = ["| agent_id | giver | feedback_time | first_tx | tx_count | wallet_age_days |",
             "|----------|-------|---------------|----------|----------|-----------------|"]
    for row in rows[:10]:
        d = dict(row)
        lines.append(
            f"| `{str(d.get('agent_id_hex',''))[-10:]}` "
            f"| `{str(d.get('giver_address',''))[:12]}...` "
            f"| {str(d.get('feedback_time',''))[:10]} "
            f"| {str(d.get('first_tx',''))[:10]} "
            f"| {d.get('tx_count','?')} "
            f"| {d.get('wallet_age_days','?')} |"
        )
    return "\n".join(lines) + "\n"


def _write_findings(findings: dict, output_path: str):
    lines = [
        "# ERC-8004 Dataset Findings",
        "",
        "> Auto-generated by `scripts/explore_dataset.py` against "
        "`bigquery-public-data.crypto_ethereum.logs`",
        f"> Contracts: IdentityRegistry `{IDENTITY_REGISTRY}` · "
        f"ReputationRegistry `{REPUTATION_REGISTRY}`",
        "",
        "---",
        "",
    ]

    # ── Q1 ────────────────────────────────────────────────────────────────────
    lines += [
        "## Q1 — Event Topics",
        "",
        "### IdentityRegistry topics",
        "",
        _format_topic_table(findings.get("id_topics")),
        "",
        "### ReputationRegistry topics",
        "",
        _format_topic_table(findings.get("rep_topics")),
        "",
        "### Raw sample — IdentityRegistry (5 rows)",
        "",
        "```json",
    ]
    id_sample = findings.get("id_sample", [])
    if isinstance(id_sample, list):
        for row in id_sample:
            lines.append(json.dumps(dict(row), default=str))
    else:
        lines.append(str(id_sample))
    lines += ["```", "", "### Raw sample — ReputationRegistry (5 rows)", "", "```json"]
    rep_sample = findings.get("rep_sample", [])
    if isinstance(rep_sample, list):
        for row in rep_sample:
            lines.append(json.dumps(dict(row), default=str))
    else:
        lines.append(str(rep_sample))
    lines += ["```", ""]

    # ── Q2 ────────────────────────────────────────────────────────────────────
    lines += [
        "## Q2 — Feedback Value Decodability",
        "",
        "### Data field length distribution",
        "",
    ]
    data_dist = findings.get("data_dist", [])
    if isinstance(data_dist, list):
        lines.append("| data_size_bucket | count |")
        lines.append("|-----------------|-------|")
        for row in data_dist:
            d = dict(row)
            lines.append(f"| {d.get('data_size_bucket')} | {d.get('count')} |")
    else:
        lines.append(str(data_dist))
    lines += ["", "### Decoded feedback values (int256 slot 0, uint8 slot 1)", ""]
    decoded = findings.get("decoded_feedback", [])
    if decoded:
        lines.append("| tx (prefix) | data_len | topic_count | int256 value | uint8 decimals | giver (topic2) | ts |")
        lines.append("|-------------|----------|-------------|-------------|----------------|----------------|----|")
        for d in decoded:
            lines.append(
                f"| `{d['tx']}` | {d['raw_data_len']} | {d['topic_count']} "
                f"| {d['decoded_int256_slot0']} | {d['decoded_uint8_slot1']} "
                f"| `{d['giver_from_topic2'][:16]}...` | {d['ts'][:10]} |"
            )
    else:
        lines.append("_No decodable data found or all data fields empty._")
    lines.append("")

    # ── Q3 ────────────────────────────────────────────────────────────────────
    lines += [
        "## Q3 — Agent Metadata / Domain Signals",
        "",
        "### IdentityRegistry non-empty data fields (sample)",
        "",
        "```json",
    ]
    id_data = findings.get("id_data", [])
    if isinstance(id_data, list):
        for row in id_data[:5]:
            lines.append(json.dumps(dict(row), default=str))
    else:
        lines.append(str(id_data))
    lines += ["```", "", "### URI events on IdentityRegistry", "", "```json"]
    uri_events = findings.get("uri_events", [])
    if isinstance(uri_events, list):
        for row in uri_events:
            lines.append(json.dumps(dict(row), default=str))
        if not uri_events:
            lines.append("(none)")
    else:
        lines.append(str(uri_events))
    lines += ["```", ""]

    # ── Q4 ────────────────────────────────────────────────────────────────────
    lines += ["## Q4 — Agents with Both Identity AND Feedback", ""]
    overlap = findings.get("overlap", [])
    if isinstance(overlap, list) and overlap:
        d = dict(overlap[0])
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total registered (IdentityRegistry mints) | {d.get('total_registered')} |",
            f"| Total with ≥1 feedback event | {d.get('total_with_feedback')} |",
            f"| **Both identity AND feedback** | **{d.get('both_identity_and_feedback')}** |",
            f"| Identity only (no feedback) | {d.get('identity_only')} |",
            f"| Feedback without registered identity | {d.get('feedback_without_identity')} |",
            "",
        ]
    else:
        lines.append(str(overlap))
        lines.append("")

    lines += ["### Top agents by feedback event count", ""]
    feedback_top = findings.get("feedback_top", [])
    if isinstance(feedback_top, list):
        lines.append("| agent_id_hex | feedback_events | distinct_givers_indexed |")
        lines.append("|--------------|-----------------|------------------------|")
        for row in feedback_top[:15]:
            d = dict(row)
            lines.append(
                f"| `{d.get('agent_id_hex','')[-20:]}` "
                f"| {d.get('feedback_events')} "
                f"| {d.get('distinct_givers_indexed')} |"
            )
    lines.append("")

    # ── Q5 ────────────────────────────────────────────────────────────────────
    lines += [
        "## Q5 — Giver-Address Join Feasibility (Sybil-Resistance Data)",
        "",
        "### Topic layout sample (which slot is giver address?)",
        "",
        "```json",
    ]
    topic_layout = findings.get("topic_layout", [])
    if isinstance(topic_layout, list):
        for row in topic_layout[:5]:
            lines.append(json.dumps(dict(row), default=str))
    else:
        lines.append(str(topic_layout))
    lines += ["```", "", "### Giver-wallet join sample (100 feedback events → tx stats)", ""]
    lines.append(_format_giver_join(findings.get("giver_join")))

    giver_count = findings.get("giver_count", [])
    if isinstance(giver_count, list) and giver_count:
        d = dict(giver_count[0])
        lines.append(f"**Distinct feedback givers across all events:** {d.get('distinct_givers')}")
    lines.append("")

    cost = findings.get("cost_estimate", {})
    if isinstance(cost, dict) and "gb_processed" in cost:
        gb = cost["gb_processed"]
        cost_usd = gb * 0.005  # BigQuery $5/TB = $0.005/GB
        lines += [
            f"**Dry-run cost estimate (full giver join):** {gb:.4f} GB scanned "
            f"≈ ${cost_usd:.4f} USD per run (first 1 TB/month free).",
            "",
        ]

    # ── Summary / Conclusions ─────────────────────────────────────────────────
    lines += [
        "---",
        "",
        "## Summary & Feasibility Conclusions",
        "",
        "> **Fill this section manually after reviewing the raw findings above.**",
        "",
        "| Question | Answer |",
        "|----------|--------|",
        "| Q1: What events exist? | _(fill after review)_ |",
        "| Q2: Feedback value decodable? | _(fill after review)_ |",
        "| Q3: Domain metadata available? | _(fill after review)_ |",
        "| Q4: Addressable ranking set size | _(fill after review)_ |",
        "| Q5: Giver-wallet join feasible? | _(fill after review)_ |",
        "",
        "### Feature 3 (Sybil scoring) prerequisites",
        "",
        "- [ ] Feedback value decoded (int256 slot 0 confirmed)",
        "- [ ] Giver address confirmed as topics[2] or topics[3]",
        "- [ ] Wallet-age join confirmed working on sample",
        "- [ ] Cost per full evaluation run within free tier",
        "",
        "### Feature 6 (Domain filter) verdict",
        "",
        "_(fill after reviewing Q3 — if no on-chain domain signal, "
        "domain must be inferred from agent URI metadata or applied only to curated agents)_",
        "",
    ]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Findings written to: {output_path}")

    # Also print a concise summary to stdout
    print("\n=== QUICK SUMMARY ===")
    if isinstance(findings.get("id_topics"), list):
        print(f"IdentityRegistry topics found: {len(findings['id_topics'])}")
        for row in findings["id_topics"]:
            d = dict(row)
            t = d.get("topic0", "")
            label = KNOWN_TOPICS.get(t, "unknown")
            print(f"  {t[:20]}... → {label}  (count={d.get('event_count')})")

    if isinstance(findings.get("rep_topics"), list):
        print(f"\nReputationRegistry topics found: {len(findings['rep_topics'])}")
        for row in findings["rep_topics"]:
            d = dict(row)
            t = d.get("topic0", "")
            label = KNOWN_TOPICS.get(t, "unknown")
            print(f"  {t[:20]}... → {label}  (count={d.get('event_count')})")

    if isinstance(findings.get("overlap"), list) and findings["overlap"]:
        d = dict(findings["overlap"][0])
        print(f"\nAddressable set (both identity+feedback): {d.get('both_identity_and_feedback')}")
        print(f"Total registered agents: {d.get('total_registered')}")
        print(f"Agents with any feedback: {d.get('total_with_feedback')}")

    if findings.get("decoded_feedback"):
        first = findings["decoded_feedback"][0]
        print(f"\nSample decoded feedback: int256={first['decoded_int256_slot0']}, "
              f"decimals={first['decoded_uint8_slot1']}, data_len={first['raw_data_len']}")

    if isinstance(findings.get("giver_join"), list) and findings["giver_join"]:
        first = dict(findings["giver_join"][0])
        print(f"\nSample giver join: wallet_age_days={first.get('wallet_age_days')}, "
              f"tx_count={first.get('tx_count')}")


if __name__ == "__main__":
    main()
