"""
File: metrics.py

Purpose:
Pure metric functions for the evaluation harness.

No database, no network - so they are unit-testable and produce identical
numbers across runs given the same inputs.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Sequence, Set

# --------------------------------------------------------------- retrieval


def hit_rate_at_k(retrieved: Sequence[int], relevant: Set[int], k: int) -> float:
    """1.0 if any relevant item appears in the top k."""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def recall_at_k(retrieved: Sequence[int], relevant: Set[int], k: int) -> float:
    """Fraction of relevant items found in the top k."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: Sequence[int], relevant: Set[int], k: int) -> float:
    """Fraction of the top k that is relevant."""
    if k <= 0:
        return 0.0
    top = retrieved[:k]
    if not top:
        return 0.0
    return len(set(top) & relevant) / len(top)


def reciprocal_rank(retrieved: Sequence[int], relevant: Set[int]) -> float:
    """1/rank of the first relevant item, else 0."""
    for position, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / position
    return 0.0


def ndcg_at_k(retrieved: Sequence[int], relevant: Set[int], k: int) -> float:
    """
    Normalised discounted cumulative gain with binary relevance.

    Rewards putting relevant chunks near the top, not merely including them.
    """
    if not relevant:
        return 0.0

    dcg = 0.0
    for position, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(position + 1)

    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(position + 1) for position in range(1, ideal_hits + 1))

    return dcg / idcg if idcg else 0.0


def aggregate_retrieval(
    results: List[Dict], k_values: Sequence[int] = (1, 3, 5, 10)
) -> Dict:
    """
    Aggregate per-query results into a metric summary.

    Each result needs: {"retrieved": [chunk_id...], "relevant": {chunk_id...}}
    """
    if not results:
        return {"queries": 0}

    summary: Dict[str, float] = {"queries": len(results)}

    for k in k_values:
        summary[f"hit_rate@{k}"] = round(
            sum(hit_rate_at_k(r["retrieved"], r["relevant"], k) for r in results) / len(results), 4
        )
        summary[f"recall@{k}"] = round(
            sum(recall_at_k(r["retrieved"], r["relevant"], k) for r in results) / len(results), 4
        )
        summary[f"precision@{k}"] = round(
            sum(precision_at_k(r["retrieved"], r["relevant"], k) for r in results) / len(results), 4
        )
        summary[f"ndcg@{k}"] = round(
            sum(ndcg_at_k(r["retrieved"], r["relevant"], k) for r in results) / len(results), 4
        )

    summary["mrr"] = round(
        sum(reciprocal_rank(r["retrieved"], r["relevant"]) for r in results) / len(results), 4
    )

    return summary


# -------------------------------------------------------------- generation

TOKEN = re.compile(r"[a-z0-9]+")

# Phrases that make a flashcard useless out of context - the card is shown
# alone, so "according to the text" has no referent.
CONTEXT_LEAKS = (
    "the text", "the passage", "the document", "the article", "the author",
    "above", "below", "this chapter", "this section", "according to the",
    "as mentioned", "as stated", "the following", "the excerpt",
)


def tokens(text: str) -> Set[str]:
    return set(TOKEN.findall((text or "").lower()))


def lexical_groundedness(answer: str, evidence: str) -> float:
    """
    Fraction of the answer's content words that appear in the evidence.

    A cheap, deterministic proxy for faithfulness. It cannot detect a correct
    paraphrase, so it is reported alongside the LLM judge rather than instead
    of it - low lexical overlap plus a high judge score usually means
    paraphrase, and low on both means hallucination.
    """
    answer_tokens = {t for t in tokens(answer) if len(t) > 3}
    if not answer_tokens:
        return 0.0
    evidence_tokens = tokens(evidence)
    return len(answer_tokens & evidence_tokens) / len(answer_tokens)


def is_self_contained(question: str) -> bool:
    """False if the question only makes sense next to its source text."""
    lowered = (question or "").lower()
    return not any(phrase in lowered for phrase in CONTEXT_LEAKS)


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def duplicate_rate(questions: Sequence[str], threshold: float = 0.7) -> float:
    """
    Fraction of questions that near-duplicate an earlier one.

    Uses token Jaccard so it stays deterministic and offline; the runtime
    dedupe in AgentTools uses embeddings.
    """
    if len(questions) < 2:
        return 0.0

    duplicates = 0
    for index, question in enumerate(questions):
        for earlier in questions[:index]:
            if jaccard(question, earlier) >= threshold:
                duplicates += 1
                break

    return round(duplicates / len(questions), 4)


def difficulty_distribution(difficulties: Sequence[str]) -> Dict[str, float]:
    if not difficulties:
        return {}
    total = len(difficulties)
    counts: Dict[str, int] = {}
    for difficulty in difficulties:
        counts[difficulty] = counts.get(difficulty, 0) + 1
    return {key: round(value / total, 4) for key, value in sorted(counts.items())}


def distribution_balance(difficulties: Sequence[str]) -> float:
    """
    How close the difficulty mix is to an even split across easy/medium/hard.

    1.0 = perfectly balanced, 0.0 = everything in one bucket. A deck that is
    95% "medium" is not actually calibrated, however good each card is.
    """
    if not difficulties:
        return 0.0

    # Computed from raw proportions, not difficulty_distribution(): its 4-dp
    # rounding leaves a perfectly balanced mix scoring 0.9999 instead of 1.0.
    total = len(difficulties)
    expected = 1 / 3
    deviation = sum(
        abs(sum(1 for d in difficulties if d == level) / total - expected)
        for level in ("easy", "medium", "hard")
    )
    # Max total deviation is 2 * (1 - 1/3) = 4/3.
    return round(max(0.0, 1 - deviation / (4 / 3)), 4)
