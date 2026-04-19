"""
File: qa_service.py

Purpose:
Handles business logic for Q&A generation and storage.
"""

from sqlalchemy.orm import Session
from ..repositories.qa_repository import QARepository
from ..ai.qa_generation.question_generator import generate_questions


class QAService:
    def __init__(self, db: Session):
        self.repo = QARepository(db)

    def generate_and_store(self, instance_id: int, chunk_text: str):
        """
        Generate Q&A from chunk and store in DB.
        """

        qa_pairs = generate_questions(chunk_text)

        if not qa_pairs:
            return []

        # Attach source chunk (optional but useful)
        for qa in qa_pairs:
            qa["source_chunk"] = chunk_text[:1000]

        return self.repo.create_many(instance_id, qa_pairs)