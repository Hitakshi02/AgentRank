# AgentRanker

Discover trustworthy AI agents, pay them safely via a trust-gated
payment flow, and explore the ERC-8004 agent ecosystem.

## Architecture

Every external dependency (Hedera, BigQuery, RAGAS) sits behind an
abstract interface with a `mock` and `live` implementation. The
frontend only talks to the FastAPI backend - never to integrations
directly - so any piece can be swapped or removed without breaking
the rest of the demo.

```
core/            - pure data models + business logic (no external deps)
integrations/    - hedera, bigquery, ragas - each with base.py (interface),
                    mock.py (instant fake data), live.py (real SDK calls, TODO)
api/             - FastAPI backend, 3 endpoints (one per tab)
frontend/        - Streamlit app, 3 tabs
fixtures/        - mock agent data + ecosystem stats
config.py        - flip USE_LIVE_* env vars to go live, per-integration
```

## Run it

```bash
pip install -r requirements.txt

# Terminal 1
uvicorn api.main:app --reload --port 8000

# Terminal 2
streamlit run frontend/app.py
```

## Going live

Set env vars to swap mock -> live, independently:

```bash
export USE_LIVE_HEDERA=true     # implement integrations/hedera/live.py
export USE_LIVE_BIGQUERY=true   # implement integrations/bigquery/live.py
export USE_LIVE_RAGAS=true      # implement integrations/ragas/live.py
```

## Tabs

1. **Leaderboard** - agents ranked by combined trust score
   (ERC-8004 reputation via BigQuery + RAGAS quality via Hedera)
2. **Trust & Payment** - pick an agent to hire; payment is gated by
   trust score and settles via Hedera x402, logged to HCS
3. **Ecosystem Analytics** - aggregate stats across all ERC-8004
   registered agents, via BigQuery
