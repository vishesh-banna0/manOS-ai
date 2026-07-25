"""
File: flashcard_repository.py

Purpose:
Handles DB operations for flashcards.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.flashcard import Flashcard


class FlashcardRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, flashcard: Flashcard) -> Flashcard:
        self.db.add(flashcard)
        self.db.commit()
        self.db.refresh(flashcard)
        return flashcard

    def bulk_create(self, flashcards: List[Flashcard]) -> List[Flashcard]:
        self.db.add_all(flashcards)
        self.db.commit()
        for flashcard in flashcards:
            self.db.refresh(flashcard)
        return flashcards

    def get_by_instance(self, instance_id: int) -> List[Flashcard]:
        return (
            self.db.query(Flashcard)
            .filter(Flashcard.instance_id == instance_id)
            .order_by(Flashcard.created_at.desc())
            .all()
        )

    def get_due_flashcards(
        self, instance_id: int, limit: Optional[int] = None
    ) -> List[Flashcard]:
        """
        Cards scheduled for review now.

        Suspended cards are excluded - the revision agent suspends a topic
        while it is being re-taught so the learner is not drilled on cards
        that are about to be replaced.
        """
        query = (
            self.db.query(Flashcard)
            .filter(
                Flashcard.instance_id == instance_id,
                Flashcard.next_review <= datetime.utcnow(),
                Flashcard.suspended.is_(False),
            )
            .order_by(Flashcard.next_review.asc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def update(self, flashcard: Flashcard) -> Flashcard:
        self.db.commit()
        self.db.refresh(flashcard)
        return flashcard
