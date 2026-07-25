"""
File: datasets.py

Purpose:
Build golden evaluation sets from an instance's indexed corpus.

The hard part of evaluating retrieval on your own corpus is ground truth. Two
strategies, both producing (query -> known relevant chunk id) pairs:

- "lexical": derive a query from a chunk's most distinctive terms, scored by
  TF-IDF against the rest of the corpus. Free, deterministic, no model needed -
  this is what runs in CI.
- "llm": ask the model to write a question answerable *only* from that chunk.
  More realistic phrasing, but costs generation time and varies between runs.

Neither is a substitute for human-labelled relevance; both are honest proxies
that detect regressions, which is what this harness is for.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..src.ai.llm.client import LLMInvalidOutput, LLMUnavailable, generate_json
from ..src.models.chunk import Chunk

TOKEN = re.compile(r"[a-z][a-z0-9\-]{2,}")

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "which", "there",
    "their", "these", "those", "have", "has", "had", "been", "were", "was",
    "are", "can", "will", "would", "should", "could", "may", "might", "must",
    "into", "than", "then", "such", "when", "where", "what", "how", "why",
    "each", "also", "some", "other", "more", "most", "only", "them", "they",
    "its", "our", "your", "his", "her", "using", "used", "use", "one", "two",
    "not", "but", "all", "any", "because", "while", "between", "over", "under",
}


@dataclass
class GoldenQuery:
    query: str
    relevant_chunk_ids: List[int]
    source: str  # "lexical" or "llm"
    chunk_title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _tokens(text: str) -> List[str]:
    return [t for t in TOKEN.findall((text or "").lower()) if t not in STOPWORDS]


def _tfidf_terms(chunk_text: str, document_frequency: Counter, total_chunks: int, top_n: int = 6):
    """Pick the terms that most distinguish this chunk from the rest."""
    counts = Counter(_tokens(chunk_text))
    if not counts:
        return []

    scored = []
    for term, count in counts.items():
        df = document_frequency.get(term, 0) or 1
        idf = math.log((total_chunks + 1) / (df + 1)) + 1.0
        scored.append((count * idf, term))

    scored.sort(reverse=True)
    return [term for _, term in scored[:top_n]]


def build_lexical_queries(
    db: Session,
    instance_id: int,
    sample_size: int = 30,
    seed: int = 42,
) -> List[GoldenQuery]:
    """
    Derive pseudo-queries from each chunk's most distinctive terms.

    Ground truth is the chunk the terms came from. Because terms are chosen by
    TF-IDF, they are rare elsewhere in the corpus - so a retriever that cannot
    find the source chunk is genuinely failing.
    """
    chunks = db.query(Chunk).filter(Chunk.instance_id == instance_id).all()
    if not chunks:
        return []

    document_frequency: Counter = Counter()
    for chunk in chunks:
        document_frequency.update(set(_tokens(chunk.text)))

    random.Random(seed).shuffle(chunks)
    selected = chunks[:sample_size]

    queries = []
    for chunk in selected:
        terms = _tfidf_terms(chunk.text, document_frequency, len(chunks))
        if len(terms) < 3:
            continue
        queries.append(
            GoldenQuery(
                query=" ".join(terms),
                relevant_chunk_ids=[chunk.id],
                source="lexical",
                chunk_title=(chunk.title or "")[:80],
            )
        )

    return queries


def build_llm_queries(
    db: Session,
    instance_id: int,
    sample_size: int = 15,
    seed: int = 42,
) -> List[GoldenQuery]:
    """Ask the model for a natural question answerable only from each chunk."""
    chunks = db.query(Chunk).filter(Chunk.instance_id == instance_id).all()
    if not chunks:
        return []

    random.Random(seed).shuffle(chunks)
    selected = chunks[:sample_size]

    def validate(payload):
        if isinstance(payload, dict):
            question = payload.get("question")
        elif isinstance(payload, list) and payload:
            question = payload[0].get("question") if isinstance(payload[0], dict) else None
        else:
            question = None

        if not isinstance(question, str) or len(question.strip()) < 10:
            raise ValueError("'question' must be a string of at least 10 characters")
        return question.strip()

    queries = []
    for chunk in selected:
        prompt = f"""Read this passage and write ONE question that can be answered
only by someone who has read it. The question must not mention "the passage"
or "the text", and must contain enough specific terms that it could be used as
a search query.

PASSAGE:
\"\"\"
{chunk.text[:3000]}
\"\"\"

Return ONLY JSON: {{"question": "..."}}"""

        try:
            question = generate_json(prompt, validate, node="eval_query_gen")
        except (LLMUnavailable, LLMInvalidOutput) as exc:
            print(f"  [datasets] skipping chunk {chunk.id}: {exc}")
            continue

        queries.append(
            GoldenQuery(
                query=question,
                relevant_chunk_ids=[chunk.id],
                source="llm",
                chunk_title=(chunk.title or "")[:80],
            )
        )

    return queries


def build_golden_set(
    db: Session,
    instance_id: int,
    strategy: str = "lexical",
    sample_size: int = 30,
    seed: int = 42,
) -> List[GoldenQuery]:
    if strategy == "llm":
        return build_llm_queries(db, instance_id, sample_size=sample_size, seed=seed)
    if strategy == "both":
        return build_lexical_queries(db, instance_id, sample_size, seed) + build_llm_queries(
            db, instance_id, max(5, sample_size // 3), seed
        )
    return build_lexical_queries(db, instance_id, sample_size=sample_size, seed=seed)


def save_golden_set(queries: List[GoldenQuery], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([q.to_dict() for q in queries], handle, indent=2, ensure_ascii=False)


def load_golden_set(path: Path) -> List[GoldenQuery]:
    with open(path, "r", encoding="utf-8") as handle:
        return [GoldenQuery(**item) for item in json.load(handle)]
