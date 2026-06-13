# AgentRanker

Discover trustworthy AI agents, pay them safely via a trust-gated
payment flow on Hedera, and explore the ERC-8004 agent ecosystem via
Google BigQuery.

## The problem

Tens of thousands of AI agents are now registered on-chain under
ERC-8004, and they're starting to pay each other autonomously for
API calls, data, and compute. But there's no circuit breaker: an
agent with zero track record can get paid just as easily as one with
a proven history. AgentRanker is that circuit breaker.

## What it does

1. **Leaderboard** - ranks agents by a combined trust score: on-chain
   ERC-8004 reputation (via BigQuery) blended with live RAGAS
   evaluation quality (faithfulness, answer relevancy, context
   precision).
2. **Trust & Payment** - before paying an agent, AgentRanker checks
   its trust score against a threshold. If it passes, payment
   settles on **Hedera Testnet** via a real HBAR transfer. Every
   decision - approved or blocked - is logged immutably to **Hedera
   Consensus Service (HCS)** as an audit trail.
3. **Ecosystem Analytics** - aggregate stats across the full ERC-8004
   dataset (registration growth, x402 adoption, reputation
   distribution).

## Architecture

```
core/            pure data models + business logic, no external deps
integrations/    hedera, bigquery, ragas - each with:
                   base.py  - abstract interface
                   mock.py  - instant fake data, shaped identically to live
                   live.py  - real SDK calls
api/             FastAPI backend, one endpoint per tab
frontend/        Streamlit app, 3 tabs
fixtures/        mock agent data + cached RAGAS scores
config.py        flip USE_LIVE_* env vars to go live, per integration
scripts/         one-time setup (e.g. creating the HCS topic)
```

Every external dependency sits behind an interface with a mock and a
live implementation, shaped identically. The frontend only talks to
the FastAPI backend - never to integrations directly - so any piece
can be swapped or removed without breaking the rest of the app.

## Payment flow (Hedera)

This is the core flow that satisfies the "AI & Agentic Payments on
Hedera" bounty:

1. A user (or another agent) requests to query a specific agent from
   the leaderboard.
2. AgentRanker computes that agent's **trust score** - a blend of its
   ERC-8004 on-chain reputation and its RAGAS evaluation scores.
3. The trust score is compared against a configurable threshold
   (`TRUST_THRESHOLD`, default `0.5`).
4. **If approved**: a real `TransferTransaction` moves a small amount
   of HBAR (0.001 HBAR) from the AgentRanker operator account to the
   target agent's Hedera account on **testnet**. This is the
   "payment" - a genuine financial operation, verifiable on
   [HashScan](https://hashscan.io/testnet).
5. **Regardless of outcome** (approved or blocked), the full decision
   - requester, target agent, trust score, threshold, approved or
   blocked, amount, transaction id, reason, timestamp - is serialized
   to JSON and submitted to an **HCS topic** via
   `TopicMessageSubmitTransaction`. This creates a permanent,
   tamper-proof audit trail of every payment decision AgentRanker has
   ever made, also verifiable on HashScan.

```
User picks agent
      |
      v
Compute trust score (BigQuery reputation + RAGAS)
      |
      v
score >= threshold? ----no----> log "blocked" decision to HCS
      |
     yes
      |
      v
HBAR transfer on Hedera Testnet (the payment)
      |
      v
log "approved" decision + tx id to HCS
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

- `HEDERA_OPERATOR_ID` / `HEDERA_OPERATOR_KEY` - your Hedera testnet
  account (get one free at portal.hedera.com)
- `HEDERA_AGENT_ACCOUNT_ID` - a second testnet account that represents
  the agent being paid
- `HEDERA_HCS_TOPIC_ID` - leave blank for now

### 3. Create the HCS audit topic (one-time)

```bash
python3 scripts/setup_hedera.py
```

Copy the printed topic ID into `.env` as `HEDERA_HCS_TOPIC_ID`.

### 4. Run it

```bash
# Terminal 1
uvicorn api.main:app --reload --port 8000

# Terminal 2
streamlit run frontend/app.py
```

By default everything runs on mocks (`USE_LIVE_*=false`) - the full
UI works instantly with no credentials needed.

### 5. Go live

```bash
export USE_LIVE_HEDERA=true
```

Now the Trust & Payment tab executes real transactions on Hedera
Testnet. Verify any `tx_id` or `hcs_message_id` from the response at
hashscan.io/testnet.

## Tech stack

- **Backend**: Python, FastAPI
- **Frontend**: Streamlit
- **Payments + audit trail**: Hedera Testnet (`hiero-sdk-python`) -
  `TransferTransaction` for payments, `TopicMessageSubmitTransaction`
  for the HCS audit log
- **Reputation data**: Google BigQuery, public Ethereum mainnet
  dataset, ERC-8004 Identity/Reputation/Validation registries
- **Evaluation**: RAGAS (faithfulness, answer relevancy, context
  precision)

## Demo

[Demo video link here]

## Built for

ETHGlobal New York 2026 - Hedera ("AI & Agentic Payments on Hedera")
and Google Cloud ("Best On-Chain Agent Economy Application") bounties.
