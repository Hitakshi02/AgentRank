"""
Sybil-resistant scoring engine for AgentRanker.

Fills the gap ERC-8004 deliberately left: "scoring should be public and
verifiable." Every function here is a pure, unit-testable computation that
traces back to on-chain data.

Components (compose in order):

  1. recency_weight        — exp(-lambda * days_ago)
  2. giver_credibility     — f(wallet_age, tx_count) → [0,1]
  3. HHI penalty           — diversity_multiplier = (1 - HHI)
  4. Bayesian shrinkage    — pull low-sample agents toward the global mean
  5. Validation bonus      — additive multiplier for ERC-8004 validated agents

Final:
  reputation_component =
      bayesian_shrinkage(feedbacks weighted by credibility × recency)
      × diversity_multiplier
      × (1 + validation_bonus)

  trust_score = w1 * reputation_component + w2 * ragas_component
               (ragas_component only where the agent has a queryable endpoint)
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ------------------------------------------------------------------
# Tunable parameters (all exposed in scoring_params on the API)
# ------------------------------------------------------------------
LAMBDA_DEFAULT     = math.log(2) / 90    # half-life = 90 days
CREDIBILITY_MAX_AGE_DAYS = 1000          # wallet age at which credibility saturates
CREDIBILITY_MAX_TX       = 500           # tx count at which credibility saturates
BAYESIAN_C               = 10.0          # prior weight; 10 ≡ "trust data after ~10 events"
VALIDATION_BONUS_DEFAULT = 0.05          # +5% for agents with validation events
W1_REPUTATION            = 0.6          # weight: on-chain reputation component
W2_RAGAS                 = 0.4          # weight: RAGAS evaluation component

HHI_SYBIL_THRESHOLD      = 0.50         # above this → flag as concentrated
CREDIBILITY_LOW_THRESHOLD = 0.10         # below this → flag as low credibility


# ------------------------------------------------------------------
# Dataclasses (kept in scoring.py to avoid circular imports with models.py)
# ------------------------------------------------------------------
@dataclass
class FeedbackEvent:
    agent_id: str
    giver_address: str
    quality_score: float    # 0-100, decoded from on-chain data slot1
    vote_weight: float      # slot0 (usually 1)
    timestamp: str          # ISO-8601 or "YYYY-MM-DD"


@dataclass
class GiverStats:
    wallet_age_days: float
    tx_count: int


@dataclass
class AgentSybilScore:
    agent_id: str
    # ── Naive metrics (what the raw on-chain data says) ──────────────
    naive_feedback_count: int
    naive_avg_quality: float        # simple mean of quality_score
    naive_score: float              # naive ranking metric (0-1)
    naive_rank: int = 0

    # ── Sybil-resistant components ───────────────────────────────────
    recency_weighted_avg: float = 0.0     # avg quality weighted by recency
    giver_credibility_avg: float = 0.0    # mean credibility of all givers
    hhi: float = 0.0                      # Herfindahl-Hirschman Index
    diversity_multiplier: float = 1.0     # (1 - HHI)
    bayesian_adjusted: float = 0.0        # Bayesian-shrunk score (0-100)
    validation_bonus: float = 0.0
    reputation_component: float = 0.0     # final composed score (0-1)
    sybil_rank: int = 0

    # ── Explanation ──────────────────────────────────────────────────
    explanation: str = ""
    flags: List[str] = field(default_factory=list)
    # e.g. ["high_hhi", "new_wallets", "low_credibility", "validated"]


@dataclass
class RankingComparison:
    naive_ranking: List[dict]    # [{rank, agent_id, score, feedback_count}, ...]
    sybil_ranking: List[dict]    # [{rank, agent_id, score, explanation, flags}, ...]
    deltas: List[dict]           # per-agent rank delta + explanation
    global_mean_quality: float
    total_feedback_events: int
    unique_givers: int
    scoring_params: dict


# ------------------------------------------------------------------
# 1. Recency decay
# ------------------------------------------------------------------
def recency_weight(days_ago: float, lambda_: float = LAMBDA_DEFAULT) -> float:
    """
    Exponential decay: exp(-λ × days_ago).
    Default λ = ln(2)/90 → feedback 90 days old has half the weight of today's.
    """
    return math.exp(-lambda_ * max(0.0, days_ago))


# ------------------------------------------------------------------
# 2. Giver credibility
# ------------------------------------------------------------------
def giver_credibility(
    wallet_age_days: float,
    tx_count: int,
    max_age: float = CREDIBILITY_MAX_AGE_DAYS,
    max_tx: int = CREDIBILITY_MAX_TX,
) -> float:
    """
    Credibility ∈ [0, 1].
    = (age_score + tx_score) / 2
    where age_score = min(wallet_age_days / max_age, 1)
    and   tx_score  = min(tx_count / max_tx, 1)

    A 3-day-old wallet with 2 txs gets ≈ 0.003 + 0.002 = 0.005 / 2 = 0.0025.
    A 1-year-old wallet with 200 txs gets ≈ 0.365 + 0.4 = 0.382.
    A 3-year-old wallet with 500+ txs gets ≈ 1.0.
    Makes Sybil attacks expensive: you need aged, active wallets, not throwaways.
    """
    age_score = min(wallet_age_days / max_age, 1.0)
    tx_score  = min(tx_count / max_tx, 1.0)
    return (age_score + tx_score) / 2.0


# ------------------------------------------------------------------
# 3. HHI (concentration / Sybil detection)
# ------------------------------------------------------------------
def compute_hhi(weighted_contributions: Dict[str, float]) -> float:
    """
    Herfindahl-Hirschman Index over feedback givers.
    HHI = Σ p_i²  where p_i = giver i's share of total weighted feedback.

    HHI → 1: one address dominates (Sybil-like).
    HHI → 0: many independent givers (organic).
    """
    total = sum(weighted_contributions.values())
    if total <= 0:
        return 1.0
    return sum((w / total) ** 2 for w in weighted_contributions.values())


# ------------------------------------------------------------------
# 4. Bayesian shrinkage
# ------------------------------------------------------------------
def bayesian_shrinkage(
    weighted_sum: float,
    total_weight: float,
    global_mean: float,
    C: float = BAYESIAN_C,
) -> float:
    """
    Pull low-sample agents toward the global mean.
    adjusted = (C × m + Σ weighted_score) / (C + Σ weight)

    Same formula as the IMDb weighted rating.
    With C=10: an agent with 2 feedbacks contributes only 2/(10+2) = 17% of its
    own data; 83% is pulled from the global mean.
    With 50 feedbacks: 50/(60) = 83% own data.
    """
    return (C * global_mean + weighted_sum) / (C + total_weight)


# ------------------------------------------------------------------
# 5. Full agent scoring
# ------------------------------------------------------------------
def _days_ago(timestamp_str: str, now: Optional[datetime] = None) -> float:
    """Parse an ISO or YYYY-MM-DD timestamp and return days elapsed."""
    if now is None:
        now = datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%d %H:%M:%S+00:00", "%Y-%m-%d"):
        try:
            ts = datetime.strptime(timestamp_str[:19], fmt[:19])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return max(0.0, (now - ts).total_seconds() / 86400.0)
        except ValueError:
            continue
    return 0.0  # unknown → treat as today


def score_one_agent(
    agent_id: str,
    feedbacks: List[FeedbackEvent],
    giver_stats_map: Dict[str, GiverStats],
    global_mean: float,
    validation_count: int = 0,
    now: Optional[datetime] = None,
    lambda_: float = LAMBDA_DEFAULT,
    C: float = BAYESIAN_C,
    validation_bonus_per_event: float = VALIDATION_BONUS_DEFAULT,
) -> AgentSybilScore:
    """
    Compute both the naive score and the Sybil-resistant reputation_component
    for a single agent, given its raw feedback events and giver wallet stats.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # ── Naive metrics ────────────────────────────────────────────────
    n = len(feedbacks)
    naive_avg = (sum(f.quality_score for f in feedbacks) / n) if n > 0 else 0.0
    # Naive score = feedback_count * avg_quality / 100, capped at 1
    naive_score = min(naive_avg / 100.0, 1.0)

    if n == 0:
        return AgentSybilScore(
            agent_id=agent_id,
            naive_feedback_count=0,
            naive_avg_quality=0.0,
            naive_score=0.0,
            reputation_component=0.0,
            explanation="No feedback events on-chain.",
        )

    # ── Per-feedback weights ─────────────────────────────────────────
    per_feedback_weight: List[float] = []
    per_giver_total: Dict[str, float] = {}    # giver → total combined weight
    credibilities: List[float] = []
    weighted_quality_sum = 0.0
    total_weight = 0.0

    for fb in feedbacks:
        da = _days_ago(fb.timestamp, now)
        r  = recency_weight(da, lambda_)

        stats = giver_stats_map.get(fb.giver_address)
        if stats:
            cred = giver_credibility(stats.wallet_age_days, stats.tx_count)
        else:
            cred = 0.05   # unknown giver → low default credibility

        combined_weight = r * cred * max(1.0, fb.vote_weight)
        per_feedback_weight.append(combined_weight)
        credibilities.append(cred)
        per_giver_total[fb.giver_address] = (
            per_giver_total.get(fb.giver_address, 0.0) + combined_weight
        )
        weighted_quality_sum += fb.quality_score * combined_weight
        total_weight += combined_weight

    recency_weighted_avg = (
        sum(f.quality_score * w for f, w in zip(feedbacks, per_feedback_weight))
        / sum(per_feedback_weight)
    ) if sum(per_feedback_weight) > 0 else naive_avg

    giver_credibility_avg = sum(credibilities) / len(credibilities)

    # ── HHI ──────────────────────────────────────────────────────────
    hhi = compute_hhi(per_giver_total)
    diversity_multiplier = max(0.0, 1.0 - hhi)

    # ── Bayesian shrinkage ───────────────────────────────────────────
    bayesian_adj = bayesian_shrinkage(
        weighted_quality_sum, total_weight, global_mean, C
    )

    # ── Validation bonus ─────────────────────────────────────────────
    val_bonus = min(0.20, validation_count * validation_bonus_per_event)

    # ── Compose reputation_component (0-1) ───────────────────────────
    rep = (bayesian_adj / 100.0) * diversity_multiplier * (1.0 + val_bonus)
    rep = round(min(1.0, max(0.0, rep)), 4)

    # ── Flags ────────────────────────────────────────────────────────
    flags: List[str] = []
    if hhi > HHI_SYBIL_THRESHOLD:
        flags.append("high_hhi")
    if giver_credibility_avg < CREDIBILITY_LOW_THRESHOLD:
        flags.append("low_credibility")
    if validation_count > 0:
        flags.append("validated")
    # "new wallets" flag: majority of givers have wallet_age < 30 days
    new_wallet_count = sum(
        1 for addr in per_giver_total
        if giver_stats_map.get(addr) and giver_stats_map[addr].wallet_age_days < 30
    )
    if new_wallet_count / max(1, len(per_giver_total)) > 0.5:
        flags.append("new_wallets")

    # ── Explanation ──────────────────────────────────────────────────
    explanation = _build_explanation(
        agent_id, n, naive_avg, recency_weighted_avg, giver_credibility_avg,
        hhi, diversity_multiplier, bayesian_adj, val_bonus, rep,
        per_giver_total, giver_stats_map, flags,
    )

    return AgentSybilScore(
        agent_id=agent_id,
        naive_feedback_count=n,
        naive_avg_quality=round(naive_avg, 2),
        naive_score=round(naive_score, 4),
        recency_weighted_avg=round(recency_weighted_avg, 2),
        giver_credibility_avg=round(giver_credibility_avg, 4),
        hhi=round(hhi, 4),
        diversity_multiplier=round(diversity_multiplier, 4),
        bayesian_adjusted=round(bayesian_adj, 2),
        validation_bonus=round(val_bonus, 4),
        reputation_component=rep,
        explanation=explanation,
        flags=flags,
    )


def _build_explanation(
    agent_id: str,
    n: int,
    naive_avg: float,
    recency_weighted_avg: float,
    cred_avg: float,
    hhi: float,
    diversity: float,
    bayesian_adj: float,
    val_bonus: float,
    rep: float,
    per_giver_total: Dict[str, float],
    giver_stats_map: Dict[str, GiverStats],
    flags: List[str],
) -> str:
    parts = [
        f"{n} feedback event(s), {len(per_giver_total)} unique giver(s).",
        f"Raw avg quality: {naive_avg:.1f}/100.",
        f"Recency-weighted avg: {recency_weighted_avg:.1f}/100.",
        f"Giver credibility (avg): {cred_avg:.3f}.",
        f"HHI (concentration): {hhi:.3f}  →  diversity multiplier: {diversity:.3f}.",
    ]

    if "high_hhi" in flags:
        # Find dominant giver
        total_w = sum(per_giver_total.values())
        top_addr, top_w = max(per_giver_total.items(), key=lambda kv: kv[1])
        share = top_w / total_w if total_w else 0
        top_stats = giver_stats_map.get(top_addr)
        age_str = (
            f"{top_stats.wallet_age_days:.0f} days old, "
            f"{top_stats.tx_count} txs"
            if top_stats else "unknown wallet age"
        )
        parts.append(
            f"WARNING: HHI={hhi:.2f} — feedback is concentrated. "
            f"Top giver controls {share*100:.0f}% of weighted feedback "
            f"({age_str})."
        )

    if "new_wallets" in flags:
        new_w = sum(
            1 for a in per_giver_total
            if giver_stats_map.get(a) and giver_stats_map[a].wallet_age_days < 30
        )
        parts.append(
            f"WARNING: {new_w}/{len(per_giver_total)} feedback givers "
            f"have wallets <30 days old — possible Sybil accounts."
        )

    if "low_credibility" in flags:
        parts.append(
            f"WARNING: Average giver credibility {cred_avg:.3f} is very low. "
            "Most givers appear to be new or inactive wallets."
        )

    parts.append(
        f"Bayesian-adjusted score: {bayesian_adj:.1f}/100 "
        f"(with C={BAYESIAN_C} prior toward global mean)."
    )
    if val_bonus > 0:
        parts.append(f"Validation bonus: +{val_bonus*100:.0f}%.")
    parts.append(f"Final reputation_component: {rep:.4f}.")

    return "  ".join(parts)


# ------------------------------------------------------------------
# 6. Score all agents and produce a RankingComparison
# ------------------------------------------------------------------
def score_all_agents(
    all_feedbacks: List[FeedbackEvent],
    giver_stats_map: Dict[str, GiverStats],
    validation_counts: Optional[Dict[str, int]] = None,
    now: Optional[datetime] = None,
    lambda_: float = LAMBDA_DEFAULT,
    C: float = BAYESIAN_C,
    w1: float = W1_REPUTATION,
    w2: float = W2_RAGAS,
) -> RankingComparison:
    """
    Score every agent that appears in all_feedbacks and return a
    RankingComparison with both naive and Sybil-resistant rankings plus
    per-agent delta explanations.
    """
    if validation_counts is None:
        validation_counts = {}
    if now is None:
        now = datetime.now(timezone.utc)

    # Group feedbacks by agent
    by_agent: Dict[str, List[FeedbackEvent]] = {}
    for fb in all_feedbacks:
        by_agent.setdefault(fb.agent_id, []).append(fb)

    # Compute global mean quality (needed for Bayesian shrinkage)
    all_scores = [fb.quality_score for fb in all_feedbacks]
    global_mean = sum(all_scores) / len(all_scores) if all_scores else 50.0

    # Score each agent
    scored: List[AgentSybilScore] = []
    for agent_id, feedbacks in by_agent.items():
        s = score_one_agent(
            agent_id, feedbacks, giver_stats_map, global_mean,
            validation_counts.get(agent_id, 0), now, lambda_, C,
        )
        scored.append(s)

    # Naive ranking: by (feedback_count * naive_avg_quality) desc
    naive_sorted = sorted(
        scored,
        key=lambda s: (s.naive_feedback_count * s.naive_avg_quality),
        reverse=True,
    )
    for i, s in enumerate(naive_sorted):
        s.naive_rank = i + 1

    # Sybil-resistant ranking: by reputation_component desc
    sybil_sorted = sorted(
        scored,
        key=lambda s: s.reputation_component,
        reverse=True,
    )
    for i, s in enumerate(sybil_sorted):
        s.sybil_rank = i + 1

    # Build comparison output
    naive_ranking = [
        {
            "rank":           s.naive_rank,
            "agent_id":       s.agent_id,
            "score":          round(s.naive_avg_quality / 100.0, 4),
            "feedback_count": s.naive_feedback_count,
            "avg_quality":    s.naive_avg_quality,
        }
        for s in naive_sorted
    ]

    sybil_ranking = [
        {
            "rank":                   s.sybil_rank,
            "agent_id":               s.agent_id,
            "score":                  s.reputation_component,
            "hhi":                    s.hhi,
            "giver_credibility_avg":  s.giver_credibility_avg,
            "diversity_multiplier":   s.diversity_multiplier,
            "bayesian_adjusted":      s.bayesian_adjusted,
            "flags":                  s.flags,
            "explanation":            s.explanation,
        }
        for s in sybil_sorted
    ]

    deltas = []
    score_map = {s.agent_id: s for s in scored}
    for s in naive_sorted:
        delta = s.naive_rank - s.sybil_rank   # positive = moved UP, negative = moved DOWN
        deltas.append({
            "agent_id":    s.agent_id,
            "naive_rank":  s.naive_rank,
            "sybil_rank":  s.sybil_rank,
            "rank_delta":  delta,   # + = moved UP (better), - = moved DOWN (penalised)
            "naive_score": round(s.naive_avg_quality / 100.0, 4),
            "sybil_score": s.reputation_component,
            "flags":       s.flags,
            "summary":     _delta_summary(s, delta),
        })

    return RankingComparison(
        naive_ranking=naive_ranking,
        sybil_ranking=sybil_ranking,
        deltas=sorted(deltas, key=lambda d: abs(d["rank_delta"]), reverse=True),
        global_mean_quality=round(global_mean, 2),
        total_feedback_events=len(all_feedbacks),
        unique_givers=len(giver_stats_map),
        scoring_params={
            "lambda_recency":     round(lambda_, 6),
            "half_life_days":     round(math.log(2) / lambda_, 1),
            "bayesian_C":         C,
            "credibility_max_age_days": CREDIBILITY_MAX_AGE_DAYS,
            "credibility_max_tx":       CREDIBILITY_MAX_TX,
            "hhi_sybil_threshold":      HHI_SYBIL_THRESHOLD,
            "w1_reputation":      w1,
            "w2_ragas":           w2,
        },
    )


def _delta_summary(s: AgentSybilScore, delta: int) -> str:
    if delta > 0:
        return (
            f"Moved UP {delta} place(s) (rank {s.naive_rank} → {s.sybil_rank}). "
            f"Givers are credible (avg credibility {s.giver_credibility_avg:.3f}). "
            f"Was undervalued by naive count-based ranking."
        )
    if delta < 0:
        reasons = []
        if "high_hhi" in s.flags:
            reasons.append(f"HHI={s.hhi:.2f} (concentration penalty)")
        if "low_credibility" in s.flags:
            reasons.append(f"avg giver credibility={s.giver_credibility_avg:.3f}")
        if "new_wallets" in s.flags:
            reasons.append("majority of givers are wallets <30 days old")
        reason_str = "; ".join(reasons) if reasons else "lower credibility-weighted score"
        return (
            f"Dropped {abs(delta)} place(s) (rank {s.naive_rank} → {s.sybil_rank}). "
            f"Reason: {reason_str}."
        )
    return f"Rank unchanged at #{s.naive_rank} in both systems."
