"""
File: retrieval_eval.py

Purpose:
Measure retrieval quality, and compare retriever configurations.

Reports recall@k, precision@k, MRR and nDCG@k against a golden set, for
several configurations at once - dense-only vs hybrid, MMR on vs off. The
comparison is the point: an absolute recall number on your own corpus means
little, but "hybrid beats dense-only by 9 points of recall@5" is a decision
you can act on.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..src.ai.rag.retriever import get_retriever
from ..src.core.config import settings
from .datasets import GoldenQuery
from .metrics import aggregate_retrieval

# name -> retriever kwargs
CONFIGURATIONS: Dict[str, Dict] = {
    "dense_only": {"keyword_weight": 0.0, "use_mmr": False},
    "hybrid": {"keyword_weight": settings.HYBRID_KEYWORD_WEIGHT, "use_mmr": False},
    "hybrid_mmr": {"keyword_weight": settings.HYBRID_KEYWORD_WEIGHT, "use_mmr": True},
}


def evaluate_configuration(
    instance_id: int,
    golden: List[GoldenQuery],
    k: int = 10,
    keyword_weight: float = 0.0,
    use_mmr: bool = False,
) -> Dict:
    """Run every golden query through one retriever configuration."""
    retriever = get_retriever(instance_id)
    results = []
    misses = []

    for item in golden:
        hits = retriever.search(
            item.query,
            k=k,
            use_mmr=use_mmr,
            keyword_weight=keyword_weight,
        )
        retrieved = [hit["chunk_id"] for hit in hits]
        relevant = set(item.relevant_chunk_ids)

        results.append({"retrieved": retrieved, "relevant": relevant})

        if not set(retrieved[:5]) & relevant:
            misses.append(
                {
                    "query": item.query[:100],
                    "expected_chunk": item.relevant_chunk_ids,
                    "got": retrieved[:5],
                    "chunk_title": item.chunk_title,
                }
            )

    summary = aggregate_retrieval(results)
    summary["misses_at_5"] = len(misses)
    return {"metrics": summary, "failures": misses[:10]}


def run_retrieval_eval(
    db: Session,
    instance_id: int,
    golden: List[GoldenQuery],
    k: int = 10,
    configurations: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """
    Evaluate all configurations and pick the best by recall@5.

    Returns a report dict ready for JSON serialisation.
    """
    configurations = configurations or CONFIGURATIONS

    if not golden:
        return {
            "queries": 0,
            "error": "Golden set is empty - is anything indexed for this instance?",
        }

    retriever = get_retriever(instance_id)
    if retriever.size == 0:
        return {
            "queries": len(golden),
            "error": "Vector index is empty. Run POST /ingestion/reindex/{instance_id}.",
        }

    report = {
        "queries": len(golden),
        "index_size": retriever.size,
        "k": k,
        "configurations": {},
    }

    for name, kwargs in configurations.items():
        report["configurations"][name] = evaluate_configuration(
            instance_id, golden, k=k, **kwargs
        )

    # Rank by recall@5, then break ties on ranking quality. On a small corpus
    # recall@5 saturates at 1.0 for every configuration, so ranking on it alone
    # would report whichever config happened to be evaluated first as "best"
    # even when another one puts the right chunk at rank 1 every time.
    def rank_key(item):
        metrics = item[1]["metrics"]
        return (
            metrics.get("recall@5", 0.0),
            metrics.get("mrr", 0.0),
            metrics.get("ndcg@5", 0.0),
            metrics.get("recall@1", 0.0),
        )

    best_name, best_payload = max(report["configurations"].items(), key=rank_key)
    report["best_configuration"] = best_name
    report["ranked_by"] = "recall@5, then MRR, nDCG@5, recall@1"

    baseline = report["configurations"].get("dense_only", {}).get("metrics", {})
    chosen = best_payload["metrics"]
    if baseline:
        report["gain_over_dense_only"] = {
            "recall@5": round(chosen.get("recall@5", 0) - baseline.get("recall@5", 0), 4),
            "recall@1": round(chosen.get("recall@1", 0) - baseline.get("recall@1", 0), 4),
            "mrr": round(chosen.get("mrr", 0) - baseline.get("mrr", 0), 4),
            "ndcg@5": round(chosen.get("ndcg@5", 0) - baseline.get("ndcg@5", 0), 4),
        }

    if len(golden) < 20:
        report["caveat"] = (
            f"Only {len(golden)} golden queries over {retriever.size} chunks - "
            f"metrics saturate easily on a corpus this small. Index more "
            f"documents before drawing conclusions."
        )

    return report
