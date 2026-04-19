"""
File: flashcard_repository.py

Purpose:
Handles DB operations for flashcards.
"""

from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from ..models.flashcard import Flashcard


class FlashcardRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, flashcard: Flashcard) -> Flashcard:
        self.db.add(flashcard)
        self.db.commit()
        self.db.refresh(flashcard)
        return flashcard

    def bulk_create(self, flashcards: List[Flashcard]):
        self.db.add_all(flashcards)
        self.db.commit()

    def get_by_instance(self, instance_id: int):
        return self.db.query(Flashcard).filter(
            Flashcard.instance_id == instance_id
        ).all()

    def get_due_flashcards(self, instance_id: int):
        return self.db.query(Flashcard).filter(
            Flashcard.instance_id == instance_id,
            Flashcard.next_review <= datetime.utcnow()
        ).all()

    def update(self, flashcard: Flashcard):
        self.db.commit()
        self.db.refresh(flashcard)
        return flashcard