"""
AgentRanker frontend - Streamlit.
Only talks to the FastAPI backend via HTTP. Never imports
integrations/ directly, so any integration can be swapped or
removed without touching this file.

Run with:
    uvicorn api.main:app --reload --port 8000   (in one terminal)
    streamlit run frontend/app.py                (in another)
"""

import requests
import streamlit as st
import pandas as pd

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="AgentRanker", layout="wide")
st.title("AgentRanker")
st.caption("Discover trustworthy AI agents. Pay them safely. Verify everything on-chain.")


def call_api(method: str, path: str, **kwargs):
    try:
        if method == "GET":
            r = requests.get(f"{API_BASE}{path}", timeout=10, **kwargs)
        else:
            r = requests.post(f"{API_BASE}{path}", timeout=10, **kwargs)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)


tab1, tab2, tab3 = st.tabs(["Leaderboard", "Trust & Payment", "Ecosystem Analytics"])


# ---------------------------------------------------------------------------
# TAB 1: Leaderboard
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Agent leaderboard")
    st.write(
        "Ranked by combined trust score: on-chain ERC-8004 reputation "
        "(via BigQuery) + live RAGAS evaluation quality (via Hedera)."
    )

    capability = st.selectbox(
        "Filter by capability",
        ["All", "rag-evaluation", "summarization"],
        key="lb_capability",
    )

    params = {} if capability == "All" else {"capability": capability}
    data, err = call_api("GET", "/leaderboard", params=params)

    if err:
        st.error(f"Could not load leaderboard: {err}")
    else:
        st.caption(
            f"Data sources — BigQuery: {data['source']['bigquery']}, "
            f"RAGAS: {data['source']['ragas']}"
        )
        rows = []
        for a in data["agents"]:
            rows.append({
                "Agent": a["name"],
                "Capability": a["capability"],
                "Trust score": round(a["trust_score"], 3),
                "ERC-8004 reputation": a["erc8004_reputation"],
                "RAGAS avg": a["ragas_average"],
                "x402 support": "yes" if a["supports_x402"] else "no",
                "Hedera identity": a["hedera_topic_id"] or "unregistered",
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)

        with st.expander("Show full agent details"):
            for a in data["agents"]:
                st.markdown(f"**{a['name']}** — `{a['agent_id']}`")
                st.write(a["description"])
                st.code(a["erc8004_address"], language=None)
                st.divider()


# ---------------------------------------------------------------------------
# TAB 2: Trust & Payment
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Trust-gated agent payment")
    st.write(
        "Pick an agent to hire. AgentRanker checks its trust score before "
        "releasing payment via Hedera (x402). Every decision — approved or "
        "blocked — is logged immutably to HCS."
    )

    data, err = call_api("GET", "/leaderboard")
    if err:
        st.error(f"Could not load agents: {err}")
    else:
        agent_options = {a["name"]: a["agent_id"] for a in data["agents"]}
        choice = st.selectbox("Select an agent to hire", list(agent_options.keys()))
        agent_id = agent_options[choice]

        selected = next(a for a in data["agents"] if a["agent_id"] == agent_id)
        col1, col2, col3 = st.columns(3)
        col1.metric("Trust score", f"{selected['trust_score']:.3f}")
        col2.metric("ERC-8004 reputation", f"{selected['erc8004_reputation']}")
        col3.metric("x402 support", "yes" if selected["supports_x402"] else "no")

        if st.button("Pay for query (USDC via Hedera x402)", type="primary"):
            result, err = call_api(
                "POST", "/pay",
                json={"target_agent_id": agent_id},
            )
            if err:
                st.error(f"Payment request failed: {err}")
            else:
                decision = result["decision"]
                st.caption(f"Hedera source: {result['source']['hedera']}")
                if decision["approved"]:
                    st.success(
                        f"Payment approved. ${decision['amount_usd']} settled.\n\n"
                        f"Tx ID: `{decision['tx_id']}`\n\n"
                        f"HCS audit log: `{decision['hcs_message_id']}`"
                    )
                else:
                    st.error(
                        f"Payment blocked.\n\n"
                        f"Reason: {decision['reason']}\n\n"
                        f"Decision still logged to HCS: `{decision['hcs_message_id']}`"
                    )


# ---------------------------------------------------------------------------
# TAB 3: Ecosystem Analytics
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("ERC-8004 ecosystem analytics")
    st.write("Aggregate stats across all agents registered on ERC-8004, via BigQuery.")

    data, err = call_api("GET", "/analytics")
    if err:
        st.error(f"Could not load analytics: {err}")
    else:
        st.caption(f"BigQuery source: {data['source']['bigquery']}")
        stats = data["stats"]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total agents registered", f"{stats['total_agents']:,}")
        col2.metric("Support x402", f"{stats['agents_with_x402']:,}")
        col3.metric("Avg reputation", f"{stats['avg_reputation']}")
        col4.metric("New (30d)", f"{stats['registrations_last_30d']:,}")

        st.markdown("**Reputation score distribution**")
        dist = stats["reputation_distribution"]
        dist_df = pd.DataFrame(
            {"Reputation range": list(dist.keys()), "Agent count": list(dist.values())}
        )
        st.bar_chart(dist_df.set_index("Reputation range"))

        x402_pct = round(100 * stats["agents_with_x402"] / stats["total_agents"], 1)
        st.info(
            f"Only {x402_pct}% of registered agents support x402 payments today — "
            "the rest have on-chain identity and reputation, but no way to get paid."
        )
