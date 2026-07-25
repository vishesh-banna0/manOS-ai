"""
File: retriever.py

Purpose:
Instance-scoped retrieval over the FAISS store.

Adds three things on top of raw vector search:
- Hybrid scoring: dense cosine blended with a lexical overlap score, so exact
  term matches (formulas, acronyms) are not lost to embedding drift.
- MMR diversification: avoids returning five near-identical chunks, which is
  the main failure mode when generating multiple cards from one topic.
- Graceful degradation: if embeddings are unavailable, falls back to pure
  keyword retrieval instead of returning nothing.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional, Sequence

import numpy as np

from ...core.config import settings
from ..embeddings.embedding_generator import (
    EmbeddingUnavailable,
    get_embedding,
    get_embeddings,
)
from .faiss_store import FAISSStore

TOKEN = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "was", "were",
    "for", "on", "with", "as", "by", "that", "this", "it", "be", "from", "at",
    "which", "what", "how", "why", "when", "does", "do", "can", "we", "you",
}


def tokenize(text: str) -> List[str]:
    return [t for t in TOKEN.findall((text or "").lower()) if t not in STOPWORDS and len(t) > 2]


def keyword_score(query_tokens: Sequence[str], text: str) -> float:
    """
    Lexical overlap in [0, 1]: fraction of distinct query terms present.

    Deliberately simple - it is a tie-breaker for dense retrieval, not a
    standalone ranker.
    """
    if not query_tokens:
        return 0.0
    body = set(tokenize(text))
    if not body:
        return 0.0
    hits = sum(1 for token in set(query_tokens) if token in body)
    return hits / len(set(query_tokens))


def _mmr(
    query_vector: np.ndarray,
    candidates: List[dict],
    vectors: Dict[int, np.ndarray],
    k: int,
    lambda_mult: float,
) -> List[dict]:
    """
    Maximal Marginal Relevance: greedily pick the candidate that maximises
    relevance to the query minus similarity to what is already selected.
    """
    selected: List[dict] = []
    pool = list(candidates)

    while pool and len(selected) < k:
        best_index = 0
        best_value = -np.inf

        for index, candidate in enumerate(pool):
            vector = vectors.get(candidate["chunk_id"])
            relevance = candidate.get("score", 0.0)

            if vector is None or not selected:
                redundancy = 0.0
            else:
                sims = [
                    float(np.dot(vector, vectors[s["chunk_id"]]))
                    for s in selected
                    if vectors.get(s["chunk_id"]) is not None
                ]
                redundancy = max(sims) if sims else 0.0

            value = lambda_mult * relevance - (1 - lambda_mult) * redundancy
            if value > best_value:
                best_value = value
                best_index = index

        selected.append(pool.pop(best_index))

    return selected


class Retriever:
    """Retrieval facade for a single learning instance."""

    def __init__(self, instance_id: int):
        self.instance_id = instance_id
        self.store = FAISSStore(instance_id)

    # ------------------------------------------------------------------ search

    def search(
        self,
        query: str,
        k: Optional[int] = None,
        use_mmr: bool = True,
        keyword_weight: Optional[float] = None,
    ) -> List[dict]:
        """
        Retrieve the top-k chunks for a query.

        Returns records with `score` (final blended), `dense_score` and
        `keyword_score` so callers - and the evaluation harness - can see why
        something ranked where it did.
        """
        query = (query or "").strip()
        if not query or self.store.size == 0:
            return []

        k = k or settings.RETRIEVAL_TOP_K
        keyword_weight = (
            settings.HYBRID_KEYWORD_WEIGHT if keyword_weight is None else keyword_weight
        )
        query_tokens = tokenize(query)

        try:
            query_embedding = get_embedding(query)
        except EmbeddingUnavailable:
            return self._keyword_only(query_tokens, k)

        candidates = self.store.search(
            query_embedding,
            k=max(k, settings.RETRIEVAL_CANDIDATES),
        )
        if not candidates:
            return []

        # Blend dense + lexical.
        for candidate in candidates:
            dense = candidate.get("score", 0.0)
            lexical = keyword_score(query_tokens, candidate.get("text", ""))
            candidate["dense_score"] = dense
            candidate["keyword_score"] = lexical
            candidate["score"] = (1 - keyword_weight) * dense + keyword_weight * lexical

        candidates.sort(key=lambda c: c["score"], reverse=True)

        if not use_mmr or len(candidates) <= k:
            return candidates[:k]

        vectors: Dict[int, np.ndarray] = {}
        for candidate in candidates:
            vector = self.store.get_vector(candidate["chunk_id"])
            if vector is not None:
                vectors[candidate["chunk_id"]] = np.asarray(vector, dtype="float32")

        return _mmr(
            np.asarray(query_embedding, dtype="float32"),
            candidates,
            vectors,
            k,
            settings.RETRIEVAL_MMR_LAMBDA,
        )

    def _keyword_only(self, query_tokens: List[str], k: int) -> List[dict]:
        """Degraded path when the embedding backend is down."""
        scored = []
        for record in self.store.all_records():
            score = keyword_score(query_tokens, record.get("text", ""))
            if score > 0:
                scored.append({**record, "score": score, "dense_score": 0.0, "keyword_score": score})
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    # ------------------------------------------------------------------ writes

    def index_chunks(self, chunks: Sequence[dict]) -> int:
        """
        Embed and index chunk dicts.

        Each chunk needs: id, text, and optionally document_id / title / pages.
        """
        if not chunks:
            return 0

        ids: List[int] = []
        texts: List[str] = []
        records: List[dict] = []

        for chunk in chunks:
            text = (chunk.get("text") or "").strip()
            if not text:
                continue
            ids.append(int(chunk["id"]))
            texts.append(text)
            records.append(
                {
                    "text": text,
                    "title": chunk.get("title") or "",
                    "document_id": chunk.get("document_id"),
                    "document_name": chunk.get("document_name") or "",
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "position": chunk.get("position"),
                }
            )

        if not ids:
            return 0

        # One batched round trip rather than one request per chunk.
        vectors = get_embeddings(texts)

        return self.store.add(ids, vectors, records)

    def remove_document(self, document_id: int) -> int:
        ids = [
            record["chunk_id"]
            for record in self.store.all_records()
            if record.get("document_id") == document_id
        ]
        return self.store.remove(ids)

    def reset(self) -> None:
        self.store.reset()

    # --------------------------------------------------------------- accessors

    @property
    def size(self) -> int:
        return self.store.size

    def stats(self) -> dict:
        return self.store.stats()


@lru_cache(maxsize=32)
def get_retriever(instance_id: int) -> Retriever:
    """
    Cached retriever per instance.

    Keeps the FAISS index resident between requests instead of re-reading it
    from disk on every search.
    """
    return Retriever(instance_id)


def invalidate_retriever(instance_id: int) -> None:
    """Drop the cached retriever so the next call reloads from disk."""
    get_retriever.cache_clear()
