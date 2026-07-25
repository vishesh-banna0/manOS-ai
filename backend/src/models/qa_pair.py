"""
File: qa_pair.py

Purpose:
Stores generated Q&A pairs for each instance.

Q&A pairs are the raw generation output. They back the adaptive test bank,
while flashcards are the spaced-repetition surface over the same material.
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from ..core.database import Base


class QAPair(Base):
    __tablename__ = "qa_pairs"

    id = Column(Integer, primary_key=True, index=True)

    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=False, index=True)

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    difficulty = Column(String(20), nullable=False)
    topic = Column(String(255), nullable=True, index=True)

    # Legacy free-text copy of the source chunk.
    source_chunk = Column(Text, nullable=True)

    # --- RAG provenance ---
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True)
    source_chunk_ids = Column(JSON, nullable=True, default=list)
    groundedness = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
