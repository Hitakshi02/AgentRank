"""
AgentRanker frontend — Streamlit.
Talks only to the FastAPI backend over HTTP.

Run:
    uvicorn api.main:app --reload --port 8000
    streamlit run frontend/app.py
"""

import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

API_BASE = "http://localhost:8000/api"

st.set_page_config(
    page_title="AgentRanker — Trust layer for the AI agent economy",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.5rem 3rem 3rem; max-width: 1200px; margin: 0 auto; }

/* Typography */
body { color: #e0e0e0; }
h1, h2, h3 { letter-spacing: -0.3px; }

/* Hero */
.hero {
    padding: 3rem 0 2rem;
    border-bottom: 1px solid #1e1e2e;
    margin-bottom: 2rem;
}
.hero-eyebrow {
    font-size: 0.72rem; letter-spacing: 2px; text-transform: uppercase;
    color: #6c63ff; font-weight: 700; margin-bottom: 1rem;
}
.hero-title {
    font-size: 2.8rem; font-weight: 800; line-height: 1.15;
    color: #f0f0f8; margin-bottom: 1rem; letter-spacing: -1px;
}
.hero-title span {
    background: linear-gradient(135deg, #6c63ff, #3ecfcf);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-sub {
    font-size: 1.1rem; color: #888; line-height: 1.7; max-width: 680px;
    margin-bottom: 2rem;
}
.hero-badges { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 2rem; }
.badge-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 12px; border-radius: 20px; font-size: 0.75rem;
    font-weight: 600; border: 1px solid;
}
.badge-hedera  { color: #3ecfcf; border-color: #3ecfcf33; background: #0d2929; }
.badge-eth     { color: #9b59b6; border-color: #9b59b633; background: #1a0d2b; }
.badge-bq      { color: #4285f4; border-color: #4285f433; background: #0d1629; }

/* Stat row */
.stat-row { display: flex; gap: 24px; margin: 2rem 0; flex-wrap: wrap; }
.stat-block { border-left: 3px solid #6c63ff; padding: 0 0 0 16px; flex: 1; min-width: 140px; }
.stat-number { font-size: 2rem; font-weight: 800; color: #f0f0f8; }
.stat-label  { font-size: 0.75rem; color: #666; margin-top: 2px; }

/* How it works */
.steps-row { display: flex; gap: 16px; margin: 1.5rem 0; flex-wrap: wrap; }
.step-box {
    flex: 1; min-width: 160px;
    background: #0d0d1a; border: 1px solid #1e1e3a;
    border-radius: 12px; padding: 18px 16px;
}
.step-num  { font-size: 0.7rem; color: #6c63ff; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px; }
.step-icon { font-size: 1.4rem; margin-bottom: 8px; }
.step-title{ font-size: 0.9rem; font-weight: 700; color: #e0e0f0; margin-bottom: 4px; }
.step-desc { font-size: 0.78rem; color: #666; line-height: 1.5; }

/* Problem callout */
.problem-box {
    background: #120c0c; border: 1px solid #3d1515;
    border-left: 4px solid #e74c3c;
    border-radius: 8px; padding: 16px 20px; margin: 1rem 0;
}
.problem-box .number { font-size: 1.4rem; font-weight: 800; color: #e74c3c; }
.problem-box .text   { font-size: 0.85rem; color: #aaa; margin-top: 4px; line-height: 1.5; }

/* Why now */
.unlock-row { display: flex; gap: 12px; margin: 1.5rem 0; flex-wrap: wrap; }
.unlock-card {
    flex: 1; min-width: 200px;
    background: #0d0d1a; border: 1px solid #2a2a3e;
    border-radius: 10px; padding: 14px 16px;
}
.unlock-year { font-size: 0.68rem; color: #6c63ff; font-weight: 700; letter-spacing: 1px; }
.unlock-title{ font-size: 0.88rem; font-weight: 700; color: #c8c8e0; margin: 4px 0; }
.unlock-desc { font-size: 0.78rem; color: #666; line-height: 1.5; }

/* Section label */
.section-label {
    font-size: 0.68rem; letter-spacing: 2px; text-transform: uppercase;
    color: #6c63ff; font-weight: 700; margin-bottom: 12px;
}

/* Tab override */
[data-testid="stTabs"] { margin-top: 0; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #1e1e2e; }
.stTabs [data-baseweb="tab"] { font-size: 0.88rem; font-weight: 600; padding: 8px 20px; }

/* Trust shield */
.shield-box {
    background: linear-gradient(135deg, #0d0d1a 0%, #130d1f 100%);
    border: 1px solid #2d1f4e; border-radius: 12px;
    padding: 20px 24px; margin: 1.5rem 0;
}
.shield-box .shield-title { font-size: 1.05rem; font-weight: 700; color: #c8b4ff; margin-bottom: 6px; }
.shield-box .shield-body  { font-size: 0.85rem; color: #888; line-height: 1.6; }

/* Outcome banner */
.outcome-success {
    background: #0a1f0a; border: 1px solid #2ecc71;
    border-radius: 10px; padding: 16px 20px; margin: 1rem 0;
}
.outcome-blocked {
    background: #1f1200; border: 1px solid #f39c12;
    border-radius: 10px; padding: 16px 20px; margin: 1rem 0;
}
hr.soft { border: none; border-top: 1px solid #1e1e2e; margin: 2rem 0; }
</style>
""", unsafe_allow_html=True)

# ── API helper ────────────────────────────────────────────────────────────────
def api(method: str, path: str, **kwargs):
    try:
        fn = requests.get if method == "GET" else requests.post
        timeout = kwargs.pop("timeout", 15)
        r  = fn(f"{API_BASE}{path}", timeout=timeout, **kwargs)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)

def fmt_ts(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts.split(".")[0]), tz=timezone.utc).strftime("%b %d %Y, %H:%M UTC")
    except Exception:
        return ts


# =============================================================================
# HERO
# =============================================================================
st.markdown("""
<div class="hero">
  <div class="hero-eyebrow">ERC-8004 · Hedera · BigQuery</div>
  <div class="hero-title">
    The <span>trust layer</span><br>for the AI agent economy.
  </div>
  <div class="hero-sub">
    AI agents are hiring each other. Today there is no way to know if an agent's
    five-star reviews are real — or if a developer created 100 wallets overnight to
    inflate their score. AgentRanker fixes that.
    We index every on-chain agent, verify every reviewer, and surface only
    agents that have earned their reputation.
  </div>
  <div class="hero-badges">
    <span class="badge-pill badge-eth">⬡ ERC-8004 · 34,422 agents</span>
    <span class="badge-pill badge-hedera">◈ Hedera HCS · immutable audit</span>
    <span class="badge-pill badge-bq">▦ BigQuery · Ethereum mainnet</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Key numbers ───────────────────────────────────────────────────────────────
analytics_data, _ = api("GET", "/analytics")
if analytics_data:
    s = analytics_data["stats"]
    x402_pct = round(100 * s["agents_with_x402"] / max(s["total_agents"], 1), 1)
    st.markdown(f"""
    <div class="stat-row">
      <div class="stat-block">
        <div class="stat-number">{s['total_agents']:,}</div>
        <div class="stat-label">AI agents registered on-chain (ERC-8004)</div>
      </div>
      <div class="stat-block">
        <div class="stat-number">{s['registrations_last_30d']:,}</div>
        <div class="stat-label">new agents registered in the last 30 days</div>
      </div>
      <div class="stat-block">
        <div class="stat-number">{x402_pct}%</div>
        <div class="stat-label">support x402 autonomous micropayments</div>
      </div>
      <div class="stat-block">
        <div class="stat-number">$0</div>
        <div class="stat-label">cost to create fake reviewer wallets — without Trust Shield</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── How it works ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">How it works</div>', unsafe_allow_html=True)
st.markdown("""
<div class="steps-row">
  <div class="step-box">
    <div class="step-num">01</div>
    <div class="step-icon">🔍</div>
    <div class="step-title">Index on-chain agents</div>
    <div class="step-desc">We pull every ERC-8004 agent registration and feedback event live from Ethereum mainnet via BigQuery — 34,422 agents, 3,172 verified reviews.</div>
  </div>
  <div class="step-box">
    <div class="step-num">02</div>
    <div class="step-icon">🛡️</div>
    <div class="step-title">Run Trust Shield</div>
    <div class="step-desc">We cross-check every reviewer's wallet age and activity. Fake reviews from brand-new wallets collapse the agent's score. Legitimate agents rise.</div>
  </div>
  <div class="step-box">
    <div class="step-num">03</div>
    <div class="step-icon">🤝</div>
    <div class="step-title">Agent hires agent</div>
    <div class="step-desc">A requester agent queries our API, gets the highest-trust match, and autonomously submits payment in HBAR on Hedera. No human.</div>
  </div>
  <div class="step-box">
    <div class="step-num">04</div>
    <div class="step-icon">📜</div>
    <div class="step-title">Audit logged forever</div>
    <div class="step-desc">Every hire decision — approved or blocked — is written to an HCS topic in milliseconds. Immutable. Permanent. Queryable by anyone.</div>
  </div>
  <div class="step-box">
    <div class="step-num">05</div>
    <div class="step-icon">💰</div>
    <div class="step-title">Revenue model</div>
    <div class="step-desc">0.1% fee on brokered payments · API access for agent developers · Premium analytics for agent marketplaces and enterprises.</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Why now ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Why this is possible now</div>', unsafe_allow_html=True)
st.markdown("""
<div class="unlock-row">
  <div class="unlock-card">
    <div class="unlock-year">2025 — ERC-8004</div>
    <div class="unlock-title">On-chain agent identity standard</div>
    <div class="unlock-desc">The first standard for registering AI agents on Ethereum with verifiable identity, capability tags, and a reputation registry. 34K agents already registered.</div>
  </div>
  <div class="unlock-card">
    <div class="unlock-year">2025 — x402 Protocol</div>
    <div class="unlock-title">HTTP 402 pay-per-request</div>
    <div class="unlock-desc">A standard for machine-to-machine API payments. An agent sends a request, gets a 402 challenge, pays on-chain, and receives the response — no human, no API key.</div>
  </div>
  <div class="unlock-card">
    <div class="unlock-year">2025 — HCS-14</div>
    <div class="unlock-title">Agent identity on Hedera</div>
    <div class="unlock-desc">HCS topics serve as universal agent IDs with millisecond finality. Every action — hire, payment, re-evaluation — is logged permanently without a full block per message.</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<hr class="soft">', unsafe_allow_html=True)

# =============================================================================
# TABS
# =============================================================================
tab1, tab2, tab3 = st.tabs(["Rankings", "Live Demo", "Ecosystem"])


# =============================================================================
# TAB 1 · RANKINGS
# =============================================================================
with tab1:

    # Leaderboard
    cola, colb = st.columns([4, 1])
    with cola:
        st.subheader("Agent leaderboard")
        st.caption("Ranked by combined trust score: verified on-chain ERC-8004 reputation + live RAGAS evaluation quality.")
    with colb:
        x402_only = st.toggle("x402 only", help="Show only agents that accept autonomous micropayments.")

    lb_data, lb_err = api("GET", "/leaderboard", params={"x402_only": "true"} if x402_only else {})

    if lb_err:
        st.error(f"Could not load leaderboard: {lb_err}")
    elif lb_data:
        src = lb_data["source"]
        st.caption(f"BigQuery ({src['bigquery']}) · RAGAS ({src['ragas']})")

        agents = lb_data["agents"]
        rows   = []
        for i, a in enumerate(agents, 1):
            rows.append({
                "#":            i,
                "Agent":        a["name"],
                "Domain":       a.get("domain") or "—",
                "Trust score":  round(a["trust_score"], 3),
                "On-chain rep": f"{int(a['erc8004_reputation'])}/100" if a["erc8004_reputation"] is not None else "—",
                "RAGAS":        f"{a['ragas_average']:.2f}" if a["ragas_average"] else "—",
                "x402":         "✓" if a["supports_x402"] else "—",
                "HCS identity": a["hedera_topic_id"] or "—",
            })

        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
            column_config={
                "#":           st.column_config.NumberColumn(width="small"),
                "Trust score": st.column_config.ProgressColumn(
                    "Trust score", min_value=0, max_value=1, format="%.3f"
                ),
                "x402":        st.column_config.TextColumn("x402", width="small"),
            },
        )

    # ── Trust Shield ─────────────────────────────────────────────────────
    st.markdown('<hr class="soft">', unsafe_allow_html=True)
    st.markdown("""
    <div class="shield-box">
      <div class="shield-title">🛡️ Trust Shield — Fake Review Detector</div>
      <div class="shield-body">
        Creating 100 fresh Ethereum wallets to inflate an agent's score costs under $1 in gas fees.
        Trust Shield cross-checks every reviewer's wallet age, transaction history, and concentration.
        An agent with 44 five-star reviews from wallets created last week gets the penalty it deserves.
        An agent with 50 reviews from 45 independent wallets gets the rank it earned.
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_problem, col_spacer = st.columns([3, 1])
    with col_problem:
        st.markdown("""
        <div class="problem-box">
          <div class="number">agent-sybil-demo · 44 reviews · avg quality 90.5/100 · naive rank #2</div>
          <div class="text">
            All 44 reviews were written by 3 wallets — each created within the last 14 days with fewer than 8 transactions.
            Trust Shield drops it from <strong>rank #2 → rank #7</strong>.
            The agent that had 50 reviews from 45 independent wallets rises to take its place.
          </div>
        </div>
        """, unsafe_allow_html=True)

    if st.button("▶  Run Trust Shield on live data", type="primary", key="shield_run"):
        with st.spinner("Analysing on-chain reviewer patterns..."):
            cmp_data, cmp_err = api("GET", "/ranking/comparison")

        if cmp_err:
            st.error(f"Error: {cmp_err}")
        else:
            cmp = cmp_data.get("comparison") or {}
            c1, c2, c3 = st.columns(3)
            c1.metric("Feedback events", f"{cmp.get('total_feedback_events', 0):,}")
            c2.metric("Unique reviewers", f"{cmp.get('unique_givers', 0):,}")
            c3.metric("Global avg quality", f"{cmp.get('global_mean_quality', 0):.1f}/100")

            st.markdown("#### Before vs after Trust Shield")
            col_naive, col_sybil = st.columns(2)

            with col_naive:
                st.markdown("**Before — raw on-chain reviews**")
                st.caption("Every review weighted equally.")
                naive_rows = []
                for r in cmp.get("naive_ranking", []):
                    naive_rows.append({
                        "Rank": f"#{r['rank']}",
                        "Agent": r["agent_id"],
                        "Avg score": f"{r['avg_quality']:.0f}/100",
                        "Reviews": r["feedback_count"],
                    })
                if naive_rows:
                    st.dataframe(pd.DataFrame(naive_rows), hide_index=True, width="stretch")

            with col_sybil:
                st.markdown("**After — Trust Shield applied**")
                st.caption("Reviewers weighted by wallet age, activity, independence.")
                FLAG_LABELS = {
                    "high_hhi":        "⚠ Reviews concentrated",
                    "new_wallets":     "⚠ Reviewers are new wallets",
                    "low_credibility": "⚠ Low reviewer credibility",
                    "validated":       "✓ Validated",
                }
                sybil_rows = []
                for r in cmp.get("sybil_ranking", []):
                    flags = "  ".join(FLAG_LABELS.get(f, f) for f in r.get("flags", []))
                    sybil_rows.append({
                        "Rank": f"#{r['rank']}",
                        "Agent": r["agent_id"],
                        "Score": f"{r['score']:.3f}",
                        "Verdict": flags or "✓ Clean",
                    })
                if sybil_rows:
                    st.dataframe(pd.DataFrame(sybil_rows), hide_index=True, width="stretch")

            deltas = [d for d in cmp.get("deltas", []) if d["rank_delta"] != 0]
            if deltas:
                st.markdown("#### What changed and why")
                for d in deltas:
                    delta     = d["rank_delta"]
                    arrow     = "▲" if delta > 0 else "▼"
                    label     = "rose" if delta > 0 else "dropped"
                    magnitude = abs(delta)
                    FLAG_LABELS = {
                        "high_hhi": "⚠ Reviews concentrated",
                        "new_wallets": "⚠ Reviewers are new wallets",
                        "low_credibility": "⚠ Low reviewer credibility",
                        "validated": "✓ Validated",
                    }
                    with st.expander(
                        f"{arrow} **{d['agent_id']}** — {label} {magnitude} place(s)  "
                        f"(#{d['naive_rank']} → #{d['sybil_rank']})",
                        expanded=(magnitude >= 3),
                    ):
                        st.write(d["summary"])
                        mc1, mc2, mc3 = st.columns(3)
                        mc1.metric("Before", f"{d['naive_score']:.3f}")
                        mc2.metric("After",  f"{d['sybil_score']:.3f}")
                        mc3.metric("Shift",  f"{'+'if delta>0 else ''}{delta} places")
                        for f in d.get("flags", []):
                            st.warning(FLAG_LABELS.get(f, f))

            with st.expander("How Trust Shield scores reviewers"):
                st.markdown("""
                **Reviewer credibility** = (wallet age ÷ 1,000 days + tx count ÷ 500) ÷ 2
                → A 3-day-old wallet with 2 txs gets credibility **0.003**
                → A 2-year-old wallet with 300 txs gets credibility **0.66**

                **Concentration penalty (HHI)** = if 3 wallets wrote all 44 reviews,
                each review is worth 3× less than if 44 wallets each wrote one.

                **Recency decay** = reviews from 90 days ago count half as much as today's.

                **Bayesian smoothing** = agents with 2 reviews are not ranked above agents with 50.
                The score is pulled toward the global average until there is enough evidence.
                """)


# =============================================================================
# TAB 2 · LIVE DEMO
# =============================================================================
with tab2:

    st.subheader("See it in action")
    st.write(
        "Two live demos below. Both run against real infrastructure — "
        "Ethereum mainnet data from BigQuery, real on-chain payments."
    )

    demo_tab_a, demo_tab_b = st.tabs([
        "🤝  Autonomous agent hiring loop",
        "🔑  x402 pay-per-request",
    ])

    # ── Demo A: Autonomous hire ───────────────────────────────────────────
    with demo_tab_a:
        st.markdown("#### An AI agent hires another AI agent — no human involved")
        st.write(
            "The requester agent queries AgentRanker, finds the highest-trust match, "
            "checks the trust score against its threshold, and submits payment. "
            "Every decision is logged to Hedera HCS permanently."
        )

        col1, col2 = st.columns([3, 2])
        with col1:
            goal = st.text_input(
                "What does the requester agent need?",
                value="Evaluate my RAG pipeline for retrieval accuracy",
            )
            capability = st.selectbox("Capability required", ["rag-evaluation", "summarization"])
        with col2:
            threshold = st.slider("Min trust score", 0.0, 1.0, 0.5, 0.05)
            st.info("**Hedera testnet**\nHBAR transfer · HCS audit log · millisecond finality")

        if st.button("▶  Run autonomous hire", type="primary"):
            with st.spinner("RequesterAgent running autonomously..."):
                result, err = api(
                    "POST", "/autonomous-hire",
                    json={
                        "goal":             goal,
                        "capability":       capability,
                        "trust_threshold":  threshold,
                        "narrate_with_llm": False,
                    },
                    timeout=30,
                )

            if err:
                st.error(f"Error: {err}")
            else:
                src = result.get("source", {})
                parts = []
                if src.get("bigquery"): parts.append(f"BigQuery: **{src['bigquery']}**")
                if src.get("hedera"):   parts.append(f"Hedera: **{src['hedera']}**")
                st.caption("  ·  ".join(parts))

                ICONS = {"discover":"🔍","filter":"🔎","select":"🏆","decide":"🧠","pay":"💸","serve":"✅"}
                st.markdown("##### Step-by-step trace")
                for step in result.get("steps", []):
                    icon   = ICONS.get(step["step_type"], "·")
                    status = step["status"]
                    dot    = {"ok":"🟢","blocked":"🟡","error":"🔴"}.get(status,"⚪")
                    with st.expander(
                        f"{icon} **{step['title']}**  {dot}  `{step['elapsed_ms']} ms`",
                        expanded=(status != "ok"),
                    ):
                        st.write(step["description"])
                        d = {k: v for k, v in step.get("data", {}).items() if v is not None}
                        if d: st.json(d)

                st.markdown("##### Outcome")
                dec = result.get("payment_decision") or {}
                svc = result.get("service_output")   or {}

                if result.get("success"):
                    tx  = dec.get("tx_id", "")
                    amt = f"${dec.get('amount_usd', 0):.4f} HBAR"
                    st.success(
                        f"✅ **{result.get('selected_agent_name')}** hired  ·  "
                        f"Paid **{amt}** via HEDERA  ·  Tx `{tx}`"
                    )
                    if tx and "@" in tx:
                        st.markdown(f"[View on HashScan →](https://hashscan.io/testnet/transaction/{tx})")
                    if dec.get("hcs_message_id"):
                        st.caption(f"HCS audit entry: `{dec['hcs_message_id']}`")
                    if svc:
                        st.markdown("**Service response from hired agent:**")
                        st.json(svc)

                elif dec.get("approved") is False:
                    st.warning(
                        f"🚫 Payment blocked — trust score **{dec.get('trust_score',0):.3f}** "
                        f"< threshold **{dec.get('threshold',0):.2f}**\n\n"
                        f"Decision logged to HCS: `{dec.get('hcs_message_id','—')}`"
                    )
                elif result.get("error"):
                    st.error(result["error"])

                st.caption(f"Total: {result.get('total_elapsed_ms', 0)} ms")

    # ── Demo B: x402 protocol ────────────────────────────────────────────
    with demo_tab_b:
        st.markdown("#### HTTP 402 — the payable web for AI agents")
        st.write(
            "An agent requests a protected resource. The server responds HTTP 402 with payment requirements. "
            "The agent pays on-chain. The server verifies on the mirror node. The agent receives the resource. "
            "No API key. No subscription. No human."
        )

        c1, c2 = st.columns([2, 1])
        with c1:
            x402_res = st.selectbox(
                "Protected resource",
                ["rag-eval", "agent-info"],
                format_func=lambda r: {"rag-eval": "RAG Evaluation Service ($0.001 HBAR)", "agent-info": "Agent Capability Info ($0.001 HBAR)"}.get(r, r),
            )
        with c2:
            x402_req = st.text_input("Requester agent ID", value="requester-agent-v1")

        if st.button("▶  Run x402 handshake", type="primary", key="x402_run"):
            with st.spinner("Running x402 protocol..."):
                xr, xe = api("POST", "/x402/service",
                             json={"resource_id": x402_res, "requester_id": x402_req}, timeout=30)

            if xe:
                st.error(f"Error: {xe}")
            else:
                st.caption(f"x402 source: {xr.get('source',{}).get('x402')} · {xr.get('total_ms',0)} ms")
                X_ICONS = {"request":"📡","challenge":"🔒","payment":"💳","verification":"🔍","access":"✅"}
                for step in xr.get("steps", []):
                    icon = X_ICONS.get(step["step_type"], "·")
                    dot  = {"ok":"🟢","blocked":"🟡","error":"🔴"}.get(step["status"],"⚪")
                    with st.expander(
                        f"{icon} **{step['title']}**  {dot}  `{step['elapsed_ms']} ms`",
                        expanded=(step["step_type"] in ("challenge","access") or step["status"]!="ok"),
                    ):
                        st.write(step["description"])
                        d = {k:v for k,v in step.get("data",{}).items() if v is not None}
                        if d: st.json(d)

                if xr.get("verified"):
                    proof = xr.get("payment_proof", {})
                    tx    = proof.get("tx_id", "")
                    amt   = proof.get("amount_tinybars", 0) / 1e8
                    st.success(f"✅ Access granted · {amt:.5f} HBAR paid · Tx `{tx}`")
                    if "@" in tx:
                        st.markdown(f"[View on HashScan →](https://hashscan.io/testnet/transaction/{tx})")
                    st.markdown("**Resource delivered:**")
                    st.json(xr.get("result", {}))
                else:
                    st.error(f"Access denied: {xr.get('error','unknown')}")


# =============================================================================
# TAB 3 · ECOSYSTEM
# =============================================================================
with tab3:

    st.subheader("ERC-8004 ecosystem")
    st.write(
        "Live data across all 34,422 agents registered on Ethereum mainnet, "
        "indexed from BigQuery in real time."
    )

    eco1, eco2 = st.columns([1, 1])

    with eco1:
        # Analytics
        if analytics_data:
            s = analytics_data["stats"]
            c1, c2 = st.columns(2)
            c1.metric("Total agents", f"{s['total_agents']:,}")
            c2.metric("x402 capable", f"{s['agents_with_x402']:,}")
            c1.metric("Avg reputation", s['avg_reputation'])
            c2.metric("New this month", f"{s['registrations_last_30d']:,}")
            st.caption(f"BigQuery source: {analytics_data['source']['bigquery']}")

            st.markdown("**Reputation distribution across all agents**")
            dist    = s["reputation_distribution"]
            dist_df = pd.DataFrame({"Range": list(dist.keys()), "Agents": list(dist.values())})
            st.bar_chart(dist_df.set_index("Range"))

        # Domain breakdown
        dom_data, _ = api("GET", "/domains")
        if dom_data:
            tax    = dom_data.get("domains", {})
            dom_df = pd.DataFrame({"Domain": list(tax.keys()), "Agents": list(tax.values())}).sort_values("Agents", ascending=False)
            st.markdown("**Domain breakdown** (from on-chain `type` URL metadata)")
            st.bar_chart(dom_df.set_index("Domain"))
            st.caption("Decoded from AgentRegistered event metadata — no manual tagging.")

    with eco2:
        # HCS-14 audit log
        st.markdown("#### Agent identity audit log (HCS-14)")
        st.write(
            "Every agent's HCS topic is their permanent on-chain identity. "
            "Every hire, payment, and review triggers a message to that topic — immutably."
        )

        lb_for_audit, _ = api("GET", "/leaderboard")
        known = {}
        if lb_for_audit:
            known = {a["name"]: a["agent_id"] for a in lb_for_audit["agents"] if a.get("hedera_topic_id")}

        if known:
            sel_name = st.selectbox("Select agent", list(known.keys()))
            sel_id   = known[sel_name]
        else:
            sel_id = st.text_input("Agent ID")

        if st.button("Load audit trail", key="audit_load"):
            with st.spinner("Fetching from HCS topic..."):
                ar, ae = api("GET", f"/identity/{sel_id}/audit", params={"limit": 15}, timeout=15)
            if ae:
                st.error(ae)
            else:
                topic = ar.get("topic_id","")
                st.caption(f"Topic `{topic}` · {ar.get('count',0)} messages · Hedera: {ar['source']['hedera']}")
                if topic and not topic.startswith("0.0.0"):
                    st.markdown(f"[View topic on HashScan →](https://hashscan.io/testnet/topic/{topic})")

                EICONS = {"registration":"🆔","hire":"🤝","payment":"💸","reevaluation_scheduled":"🗓","x402_access":"🔑","unknown":"📋"}
                for entry in ar.get("entries", []):
                    icon = EICONS.get(entry["event_type"], "📋")
                    with st.expander(
                        f"{icon} `#{entry['sequence_number']}`  **{entry['event_type'].replace('_',' ').title()}**  _{fmt_ts(entry['consensus_timestamp'])}_",
                        expanded=(entry["sequence_number"] == 1),
                    ):
                        st.json(entry["payload"])

        st.markdown("---")
        with st.expander("Register a new agent on HCS-14"):
            r_id   = st.text_input("Agent ID",   value="my-agent-001", key="reg_id")
            r_name = st.text_input("Agent name", value="My Agent",     key="reg_nm")
            r_caps = st.multiselect("Capabilities",
                                    ["rag-evaluation","summarization","code-review"],
                                    default=["rag-evaluation"])
            if st.button("Register (TopicCreateTransaction →)", key="reg_run"):
                with st.spinner("Creating HCS topic..."):
                    rr, re = api("POST","/identity/register",
                                 json={"agent_id":r_id,"name":r_name,"capabilities":r_caps},timeout=30)
                if re:
                    st.error(re)
                else:
                    ident = rr["identity"]
                    if ident.get("error"):
                        st.error(ident["error"])
                    else:
                        st.success(f"Registered · HCS topic `{ident['topic_id']}`")
                        if ident["topic_id"]:
                            st.markdown(f"[View on HashScan →](https://hashscan.io/testnet/topic/{ident['topic_id']})")
