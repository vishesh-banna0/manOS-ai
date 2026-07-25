"""
File: flashcard.py

Purpose:
Flashcards with SM-2 spaced-repetition state and RAG provenance.

Provenance fields (source_chunk_ids, groundedness) exist because cards are
authored from retrieved context - storing which chunks supported a card lets
the UI cite them and lets the evaluation harness re-check groundedness later.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)

from ..core.database import Base


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)

    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=False, index=True)
    qa_pair_id = Column(
        Integer, ForeignKey("qa_pairs.id", ondelete="SET NULL"), nullable=True
    )

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    topic = Column(String(255), nullable=True, index=True)
    difficulty = Column(String(20), nullable=True)

    # --- RAG provenance ---
    # Chunk ids that grounded this card, and the critic's groundedness score.
    source_chunk_ids = Column(JSON, nullable=True, default=list)
    groundedness = Column(Float, nullable=True)
    # "agent" (authored by the flashcard agent) or "qa_pair" (legacy path).
    origin = Column(String(32), nullable=False, default="agent")

    # --- SM-2 spaced repetition state ---
    ease_factor = Column(Float, default=2.5, nullable=False)
    interval = Column(Integer, default=0, nullable=False)  # days
    repetitions = Column(Integer, default=0, nullable=False)
    lapses = Column(Integer, default=0, nullable=False)

    next_review = Column(DateTime, default=datetime.utcnow, index=True)
    last_reviewed = Column(DateTime, nullable=True)

    # Set by the revision agent when a topic is being re-taught instead of
    # merely rescheduled.
    suspended = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Flashcard(id={self.id}, topic={self.topic!r})>"
