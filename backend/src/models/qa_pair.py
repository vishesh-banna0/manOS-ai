"""
File: qa_pair.py

Purpose:
Stores generated Q&A pairs for each instance.
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from ..core.database import Base


class QAPair(Base):
    __tablename__ = "qa_pairs"

    id = Column(Integer, primary_key=True, index=True)

    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=False)

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    difficulty = Column(String(20), nullable=False)
    topic = Column(String(255), nullable=True)

    source_chunk = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())