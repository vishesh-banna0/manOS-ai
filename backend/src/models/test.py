"""
File: test.py

Purpose:
Adaptive test sessions and their questions.

The frontend has always called POST /instances/{id}/tests and
POST /tests/{id}/submit; these tables are what make those endpoints real.
Test results feed instance.last_score and the analytics/effectiveness views.
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
from sqlalchemy.orm import relationship

from ..core.database import Base


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)

    instance_id = Column(
        Integer, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False, index=True
    )

    question_count = Column(Integer, nullable=False, default=0)
    score = Column(Float, nullable=True)  # percentage 0-100
    correct_count = Column(Integer, nullable=True)

    # How question difficulty was chosen for this session, e.g.
    # "adaptive:weak-topics" or "adaptive:baseline".
    strategy = Column(String(64), nullable=False, default="adaptive")

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    questions = relationship(
        "TestQuestion",
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="TestQuestion.position",
    )

    def __repr__(self):
        return f"<Test(id={self.id}, instance={self.instance_id}, score={self.score})>"


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, index=True)

    test_id = Column(
        Integer, ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qa_pair_id = Column(
        Integer, ForeignKey("qa_pairs.id", ondelete="SET NULL"), nullable=True
    )

    position = Column(Integer, nullable=False, default=0)

    question = Column(Text, nullable=False)
    # Multiple-choice options; correct_index points into this list.
    options = Column(JSON, nullable=False, default=list)
    correct_index = Column(Integer, nullable=False, default=0)

    topic = Column(String(255), nullable=True)
    difficulty = Column(String(20), nullable=True)

    selected_index = Column(Integer, nullable=True)
    is_correct = Column(Boolean, nullable=True)

    test = relationship("Test", back_populates="questions")

    def __repr__(self):
        return f"<TestQuestion(id={self.id}, test={self.test_id})>"
