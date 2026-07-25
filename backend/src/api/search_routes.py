"""
File: search_routes.py

Purpose:
Knowledge search endpoints over an instance's indexed corpus.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    k: Optional[int] = Field(None, ge=1, le=20)


@router.get("/{instance_id}")
def search(
    instance_id: int,
    q: str = Query(..., min_length=1, description="Search query"),
    k: int = Query(5, ge=1, le=20),
    mmr: bool = Query(True, description="Diversify results with MMR"),
    db: Session = Depends(get_db),
):
    """Vector + keyword hybrid search returning chunks with provenance."""
    return SearchService(db).search(instance_id, q, k=k, use_mmr=mmr)


@router.post("/{instance_id}/answer")
def answer(instance_id: int, payload: AnswerRequest, db: Session = Depends(get_db)):
    """RAG question answering: retrieve, then answer citing the sources."""
    result = SearchService(db).answer(instance_id, payload.question, k=payload.k)
    if result.get("answer") is None and result.get("warning"):
        # Still 200 - the sources are useful even when generation is down.
        return result
    return result


@router.get("/{instance_id}/chunks")
def list_chunks(
    instance_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Browse the indexed chunks for an instance."""
    return SearchService(db).list_chunks(instance_id, limit=limit, offset=offset)
