"""
File: flashcard_routes.py

Purpose:
API endpoints for flashcard operations.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..ai.llm.client import LLMUnavailable
from ..core.database import SessionLocal, get_db
from ..models.flashcard import Flashcard
from ..services.flashcard_service import FlashcardService
from ..services.job_service import JobAlreadyRunning, jobs

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


class ReviewRequest(BaseModel):
    flashcard_id: int
    correct: bool
    # Optional SM-2 recall quality (0-5). Derived from `correct` when absent.
    quality: Optional[int] = Field(None, ge=0, le=5)
    response_ms: Optional[int] = Field(None, ge=0)


def _present(flashcard: Flashcard) -> dict:
    return {
        "id": flashcard.id,
        "instance_id": flashcard.instance_id,
        "question": flashcard.question,
        "answer": flashcard.answer,
        "topic": flashcard.topic,
        "difficulty": flashcard.difficulty,
        "source_chunk_ids": flashcard.source_chunk_ids or [],
        "groundedness": flashcard.groundedness,
        "origin": flashcard.origin,
        "ease_factor": flashcard.ease_factor,
        "interval": flashcard.interval,
        "repetitions": flashcard.repetitions,
        "lapses": flashcard.lapses,
        "next_review": flashcard.next_review.isoformat() if flashcard.next_review else None,
        "last_reviewed": flashcard.last_reviewed.isoformat() if flashcard.last_reviewed else None,
    }


@router.post("/generate/{instance_id}", status_code=202)
def generate_flashcards(
    instance_id: int,
    max_topics: Optional[int] = Query(None, ge=1, le=40),
    document_id: Optional[int] = Query(None, ge=1),
    wait: bool = Query(
        False,
        description="Block until the run finishes instead of returning a job id",
    ),
    db: Session = Depends(get_db),
):
    """
    Author flashcards with the retrieval-grounded agent.

    Returns 202 with a job id immediately: a run makes several local LLM calls
    per topic and takes minutes, which is far too long to hold an HTTP request
    open. Poll GET /jobs/{job_id} for progress.

    Pass ?wait=true for scripts that would rather block for the full run.
    """
    service = FlashcardService(db)

    # Validate up front so an impossible run fails now, not in a worker thread.
    try:
        service.assert_ready(instance_id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if wait:
        try:
            result = service.generate(instance_id, max_topics=max_topics, document_id=document_id)
        except LLMUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        return {"message": f"{result['cards_created']} flashcards created", **result}

    def task(handle):
        # A background thread must not reuse the request-scoped session, which
        # is closed as soon as this handler returns.
        session = SessionLocal()
        try:
            return FlashcardService(session).generate(
                instance_id,
                max_topics=max_topics,
                progress=handle.report,
                document_id=document_id,
            )
        finally:
            session.close()

    try:
        job = jobs.run_in_background("flashcards", task, key=f"flashcards:{instance_id}")
    except JobAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "message": "Flashcard generation started",
        "job_id": job.id,
        "poll": f"/jobs/{job.id}",
    }


@router.get("/{instance_id}")
def get_due_flashcards(
    instance_id: int,
    limit: Optional[int] = Query(None, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Cards due for review now."""
    cards = FlashcardService(db).get_due_flashcards(instance_id, limit=limit)
    return [_present(card) for card in cards]


@router.get("/{instance_id}/all")
def get_all_flashcards(instance_id: int, db: Session = Depends(get_db)):
    """Every card in the instance, due or not."""
    return [_present(card) for card in FlashcardService(db).get_all(instance_id)]


@router.post("/review")
def review_flashcard(payload: ReviewRequest, db: Session = Depends(get_db)):
    """Grade a review with SM-2 and append it to the review log."""
    flashcard = FlashcardService(db).review_flashcard(
        payload.flashcard_id,
        payload.correct,
        quality=payload.quality,
        response_ms=payload.response_ms,
    )
    if not flashcard:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    return {"message": "Flashcard updated successfully", "flashcard": _present(flashcard)}


@router.delete("/{flashcard_id}")
def delete_flashcard(flashcard_id: int, db: Session = Depends(get_db)):
    if not FlashcardService(db).delete_flashcard(flashcard_id):
        raise HTTPException(status_code=404, detail="Flashcard not found")
    return {"message": "Flashcard deleted"}
