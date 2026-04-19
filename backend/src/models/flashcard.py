"""
File: flashcard.py

Purpose:
Represents flashcards derived from QAPairs with spaced repetition metadata.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from datetime import datetime, timedelta
from ..core.database import Base


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)

    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=False)

    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)

    # Spaced repetition fields
    ease_factor = Column(Float, default=2.5)
    interval = Column(Integer, default=1)  # days
    repetitions = Column(Integer, default=0)

    next_review = Column(DateTime, default=datetime.utcnow)
    last_reviewed = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)