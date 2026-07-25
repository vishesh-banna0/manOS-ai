"""
File: review_log.py

Purpose:
Append-only record of every flashcard review.

The Flashcard row only holds current scheduler state (interval, ease, next
review). That is enough to schedule, but not to answer "is this person
actually learning?". This table is the substrate for:
- topic-level analytics and weak-area detection
- the revision planning agent
- the learning-effectiveness evaluation (retention, lapse rate)
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from ..core.database import Base


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, index=True)

    instance_id = Column(
        Integer, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flashcard_id = Column(
        Integer, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False, index=True
    )

    correct = Column(Boolean, nullable=False)
    # SM-2 recall quality 0-5; derived from `correct` when the client only
    # sends a boolean.
    quality = Column(Integer, nullable=False, default=0)

    # Denormalised so topic analytics does not need a join through flashcards
    # for every aggregate.
    topic = Column(String(255), nullable=True, index=True)
    difficulty = Column(String(20), nullable=True)

    # Scheduler state transition, kept for effectiveness evaluation.
    interval_before = Column(Integer, nullable=True)
    interval_after = Column(Integer, nullable=True)
    ease_before = Column(Float, nullable=True)
    ease_after = Column(Float, nullable=True)

    response_ms = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<ReviewLog(card={self.flashcard_id}, correct={self.correct})>"
