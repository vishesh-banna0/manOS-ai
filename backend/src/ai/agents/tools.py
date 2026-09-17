"""
File: tools.py

Purpose:
The tool surface available to agents.

Agents do not touch SQLAlchemy or FAISS directly. They call these functions,
which keeps each agent node testable in isolation (the evaluation harness
swaps in fakes) and keeps the persistence rules in one place.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from ...core.config import settings
from ...models.chunk import Chunk
from ...models.flashcard import Flashcard
from ...models.qa_pair import QAPair
from ...models.review_log import ReviewLog
from ..embeddings.embedding_generator import (
    EmbeddingUnavailable,
    cosine_similarity,
    get_embedding,
    get_embeddings,
)
from ..rag.retriever import get_retriever, keyword_score, tokenize


class AgentTools:
    """Tool implementations bound to one database session and instance."""

    def __init__(self, db: Session, instance_id: int, document_id: Optional[int] = None):
        self.db = db
        self.instance_id = instance_id
        self.document_id = document_id
        self._retriever = None
        # Cache of question -> embedding for semantic dedupe within a run.
        self._question_vectors: Dict[str, List[float]] = {}
        self._embeddings_unavailable = False

    @property
    def retriever(self):
        if self._retriever is None:
            self._retriever = get_retriever(self.instance_id)
        return self._retriever

    # ------------------------------------------------------------ retrieval

    def search_corpus(self, query: str, k: Optional[int] = None) -> List[dict]:
        """Retrieve grounding chunks for a query."""
        matches = self.retriever.search(
            query, k=k or settings.RETRIEVAL_TOP_K, document_id=self.document_id
        )
        if matches:
            return matches
        # Uploads retain chunks when Ollama/indexing is unavailable. Those
        # chunks remain usable as grounded evidence through lexical retrieval.
        tokens = tokenize(query)
        scored = []
        for row in self._chunks().all():
            score = keyword_score(tokens, row.text)
            if score > 0:
                scored.append({"chunk_id": row.id, "text": row.text, "score": score,
                               "document_id": row.document_id, "page_start": row.page_start,
                               "page_end": row.page_end})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:k or settings.RETRIEVAL_TOP_K]

    def _chunks(self):
        query = self.db.query(Chunk).filter(Chunk.instance_id == self.instance_id)
        if self.document_id is not None:
            query = query.filter(Chunk.document_id == self.document_id)
        return query

    def corpus_outline(self, limit: int = 60) -> List[dict]:
        """
        A compact map of the corpus for the planner: chunk titles + page ranges.

        Sending full chunk text for a whole document would blow the context
        window, so the planner reasons over titles and picks topics; the
        author node then pulls the real text via retrieval.
        """
        rows = (
            self._chunks()
            .order_by(Chunk.document_id, Chunk.position)
            .limit(limit)
            .all()
        )
        return [
            {
                "chunk_id": row.id,
                "title": row.title,
                "page_start": row.page_start,
                "page_end": row.page_end,
                "words": row.word_count,
            }
            for row in rows
        ]

    def corpus_size(self) -> int:
        return (
            self._chunks().with_entities(func.count(Chunk.id))
            .scalar()
            or 0
        )

    # ---------------------------------------------------------------- cards

    def existing_cards(self) -> List[Flashcard]:
        return (
            self.db.query(Flashcard)
            .filter(Flashcard.instance_id == self.instance_id)
            .all()
        )

    def existing_questions(self) -> List[str]:
        return [question for (question,) in self.db.query(Flashcard.question)
                .filter(Flashcard.instance_id == self.instance_id).all()]

    def prepare_question_vectors(self, questions: Sequence[str]) -> None:
        """Embed uncached questions in batches, with one outage fallback per run."""
        if self._embeddings_unavailable:
            return
        missing = list(dict.fromkeys(q for q in questions if q not in self._question_vectors))
        if not missing:
            return
        try:
            vectors = get_embeddings(missing)
        except EmbeddingUnavailable:
            self._embeddings_unavailable = True
            return
        self._question_vectors.update(zip(missing, vectors))

    def _question_vector(self, question: str) -> Optional[List[float]]:
        if question in self._question_vectors:
            return self._question_vectors[question]
        if self._embeddings_unavailable:
            return None
        try:
            vector = get_embedding(question)
        except EmbeddingUnavailable:
            self._embeddings_unavailable = True
            return None
        self._question_vectors[question] = vector
        return vector

    def is_duplicate(
        self,
        question: str,
        against: Sequence[str],
        threshold: Optional[float] = None,
    ) -> tuple[bool, float, Optional[str]]:
        """
        Semantic duplicate check.

        The pre-existing code deduplicated on exact string equality, so any
        paraphrase slipped through. This compares question embeddings and falls
        back to token overlap when embeddings are unavailable.

        Returns: (is_duplicate, best_similarity, matched_question)
        """
        threshold = threshold or settings.AGENT_DUPLICATE_THRESHOLD
        if not against:
            return False, 0.0, None

        normalized = question.strip().lower()
        for candidate in against:
            if candidate.strip().lower() == normalized:
                return True, 1.0, candidate

        self.prepare_question_vectors([question, *against])
        if self._embeddings_unavailable:
            return self._lexical_duplicate(question, against, threshold)
        vector = self._question_vector(question)
        if vector is None:
            return self._lexical_duplicate(question, against, threshold)

        best_score = 0.0
        best_match = None
        for candidate in against:
            candidate_vector = self._question_vector(candidate)
            if candidate_vector is None:
                continue
            score = cosine_similarity(vector, candidate_vector)
            if score > best_score:
                best_score = score
                best_match = candidate

        return best_score >= threshold, best_score, best_match

    @staticmethod
    def _lexical_duplicate(question: str, against: Sequence[str], threshold: float):
        """Jaccard fallback when the embedding backend is down."""
        def tokens(text: str) -> set:
            return {t for t in text.lower().split() if len(t) > 2}

        target = tokens(question)
        if not target:
            return False, 0.0, None

        best_score = 0.0
        best_match = None
        for candidate in against:
            other = tokens(candidate)
            if not other:
                continue
            score = len(target & other) / len(target | other)
            if score > best_score:
                best_score = score
                best_match = candidate

        return best_score >= threshold, best_score, best_match

    def save_flashcards(self, cards: Sequence[dict]) -> List[Flashcard]:
        """
        Persist accepted cards along with their Q&A pair and provenance.

        Each card also becomes a QAPair so the adaptive test bank stays in sync
        with the flashcard deck.
        """
        if not cards:
            return []

        saved: List[Flashcard] = []

        for card in cards:
            qa_pair = QAPair(
                instance_id=self.instance_id,
                question=card["question"],
                answer=card["answer"],
                difficulty=card.get("difficulty", "medium"),
                topic=card.get("topic"),
                source_chunk=(card.get("evidence") or "")[:2000] or None,
                source_chunk_ids=card.get("source_chunk_ids") or [],
                groundedness=card.get("groundedness"),
            )
            chunk_ids = card.get("source_chunk_ids") or []
            if chunk_ids:
                qa_pair.chunk_id = chunk_ids[0]

            self.db.add(qa_pair)
            self.db.flush()  # assign qa_pair.id without committing yet

            flashcard = Flashcard(
                instance_id=self.instance_id,
                qa_pair_id=qa_pair.id,
                question=card["question"],
                answer=card["answer"],
                topic=card.get("topic"),
                difficulty=card.get("difficulty", "medium"),
                source_chunk_ids=chunk_ids,
                groundedness=card.get("groundedness"),
                origin=card.get("origin", "agent"),
                next_review=datetime.utcnow(),
            )
            self.db.add(flashcard)
            saved.append(flashcard)

        self.db.commit()
        for flashcard in saved:
            self.db.refresh(flashcard)

        return saved

    # -------------------------------------------------------------- history

    def review_history(self, days: int = 60) -> List[ReviewLog]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(ReviewLog)
            .filter(
                ReviewLog.instance_id == self.instance_id,
                ReviewLog.reviewed_at >= cutoff,
            )
            .order_by(ReviewLog.reviewed_at.desc())
            .all()
        )

    def topic_performance(self, days: int = 60) -> List[dict]:
        """
        Per-topic accuracy from the review log.

        This is the evidence the revision and recommendation agents reason
        over - not the model's guess about what is hard.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            self.db.query(
                ReviewLog.topic,
                func.count(ReviewLog.id).label("reviews"),
                func.sum(func.cast(ReviewLog.correct, Integer)).label("correct"),
            )
            .filter(
                ReviewLog.instance_id == self.instance_id,
                ReviewLog.reviewed_at >= cutoff,
                ReviewLog.topic.isnot(None),
            )
            .group_by(ReviewLog.topic)
            .all()
        )

        performance = []
        for topic, reviews, correct in rows:
            reviews = int(reviews or 0)
            correct = int(correct or 0)
            if reviews == 0:
                continue
            performance.append(
                {
                    "topic": topic,
                    "reviews": reviews,
                    "correct": correct,
                    "accuracy": round(correct / reviews, 4),
                }
            )

        performance.sort(key=lambda item: item["accuracy"])
        return performance

    def due_counts(self) -> dict:
        now = datetime.utcnow()
        due = (
            self.db.query(func.count(Flashcard.id))
            .filter(
                Flashcard.instance_id == self.instance_id,
                Flashcard.next_review <= now,
                Flashcard.suspended.is_(False),
            )
            .scalar()
            or 0
        )
        total = (
            self.db.query(func.count(Flashcard.id))
            .filter(Flashcard.instance_id == self.instance_id)
            .scalar()
            or 0
        )
        return {"due": int(due), "total": int(total)}

    def cards_for_topic(self, topic: str) -> List[Flashcard]:
        return (
            self.db.query(Flashcard)
            .filter(
                Flashcard.instance_id == self.instance_id,
                Flashcard.topic == topic,
            )
            .all()
        )

    def reschedule_topic(self, topic: str, days_from_now: int) -> int:
        """Move a topic's cards earlier/later in the schedule."""
        cards = self.cards_for_topic(topic)
        target = datetime.utcnow() + timedelta(days=max(0, days_from_now))
        for card in cards:
            card.next_review = target
        self.db.commit()
        return len(cards)
