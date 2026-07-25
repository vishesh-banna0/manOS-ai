"""
File: flashcard_service.py

Purpose:
Flashcard generation (via the authoring agent) and spaced-repetition review.

Generation delegates to FlashcardAgent, which is retrieval-grounded. The old
path - "3 questions per chunk, dedupe on exact question string" - produced
hundreds of near-duplicate cards on a long PDF and is gone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..ai.agents.flashcard_agent import run_flashcard_agent
from ..ai.scheduling.sm2 import SchedulerState, quality_from_bool, review
from ..models.chunk import Chunk
from ..models.flashcard import Flashcard
from ..models.review_log import ReviewLog
from ..repositories.flashcard_repository import FlashcardRepository


class FlashcardService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FlashcardRepository(db)

    # ----------------------------------------------------------- generation

    def assert_ready(self, instance_id: int) -> None:
        """
        Raise if there is nothing to author from.

        Checked before a job is queued so the user gets an immediate 400
        instead of a background job that fails seconds later.
        """
        indexed_chunks = (
            self.db.query(func.count(Chunk.id))
            .filter(Chunk.instance_id == instance_id)
            .scalar()
            or 0
        )

        if indexed_chunks == 0:
            raise ValueError(
                "No indexed content for this instance. Upload a document first "
                "(POST /documents/upload/{instance_id})."
            )

    def generate(
        self,
        instance_id: int,
        max_topics: Optional[int] = None,
        progress=None,
    ) -> Dict:
        """
        Run the retrieval-grounded authoring agent for this instance.

        Raises:
            ValueError: nothing has been ingested yet.
        """
        self.assert_ready(instance_id)
        return run_flashcard_agent(
            self.db, instance_id, max_topics=max_topics, progress=progress
        )

    # --------------------------------------------------------------- review

    def get_due_flashcards(
        self, instance_id: int, limit: Optional[int] = None
    ) -> List[Flashcard]:
        return self.repo.get_due_flashcards(instance_id, limit=limit)

    def get_all(self, instance_id: int) -> List[Flashcard]:
        return self.repo.get_by_instance(instance_id)

    def review_flashcard(
        self,
        flashcard_id: int,
        correct: bool,
        quality: Optional[int] = None,
        response_ms: Optional[int] = None,
    ) -> Optional[Flashcard]:
        """
        Grade a review with SM-2 and append to the review log.

        `quality` (0-5) is honoured when the client sends it; otherwise it is
        derived from the boolean.
        """
        flashcard = (
            self.db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
        )
        if not flashcard:
            return None

        graded_quality = (
            int(quality) if quality is not None else quality_from_bool(correct)
        )

        state = SchedulerState(
            repetitions=flashcard.repetitions or 0,
            interval=flashcard.interval or 0,
            ease_factor=flashcard.ease_factor or 2.5,
            lapses=flashcard.lapses or 0,
        )
        update = review(state, graded_quality)

        log = ReviewLog(
            instance_id=flashcard.instance_id,
            flashcard_id=flashcard.id,
            correct=bool(correct),
            quality=graded_quality,
            topic=flashcard.topic,
            difficulty=flashcard.difficulty,
            interval_before=state.interval,
            interval_after=update.interval,
            ease_before=state.ease_factor,
            ease_after=update.ease_factor,
            response_ms=response_ms,
            reviewed_at=datetime.utcnow(),
        )

        flashcard.repetitions = update.repetitions
        flashcard.interval = update.interval
        flashcard.ease_factor = update.ease_factor
        flashcard.lapses = update.lapses
        flashcard.next_review = update.next_review
        flashcard.last_reviewed = log.reviewed_at

        self.db.add(log)
        self.db.commit()
        self.db.refresh(flashcard)

        return flashcard

    # --------------------------------------------------------------- delete

    def delete_flashcard(self, flashcard_id: int) -> bool:
        flashcard = (
            self.db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
        )
        if not flashcard:
            return False

        self.db.query(ReviewLog).filter(ReviewLog.flashcard_id == flashcard_id).delete()
        self.db.delete(flashcard)
        self.db.commit()
        return True
