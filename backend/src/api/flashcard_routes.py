"""
File: flashcard_routes.py

Purpose:
API endpoints for flashcard operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..services.flashcard_service import FlashcardService

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


@router.post("/generate/{instance_id}")
def generate_flashcards(instance_id: int, db: Session = Depends(get_db)):
    service = FlashcardService(db)
    try:
        count = service.generate_from_qa(instance_id)
        return {"message": f"{count} flashcards created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{instance_id}")
def get_flashcards(instance_id: int, db: Session = Depends(get_db)):
    service = FlashcardService(db)
    flashcards = service.get_due_flashcards(instance_id)
    return flashcards


@router.post("/review")
def review_flashcard(
    flashcard_id: int = Query(...),
    correct: bool = Query(...),
    db: Session = Depends(get_db)
):
    service = FlashcardService(db)
    result = service.review_flashcard(flashcard_id, correct)

    if not result:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    return {"message": "Flashcard updated successfully"}
