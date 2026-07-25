"""
File: agent_routes.py

Purpose:
Endpoints that run the agentic workflows.

These are slow (many local LLM calls) and deliberately synchronous - the caller
gets the full run report, including the agent trace, so behaviour is
inspectable rather than a black box.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..ai.agents.recommendation_agent import run_recommendation_agent
from ..ai.agents.revision_agent import run_revision_agent
from ..ai.llm.client import LLMUnavailable
from ..core.database import get_db
from ..services.flashcard_service import FlashcardService

router = APIRouter(prefix="/agents", tags=["Agents"])


class FlashcardAgentRequest(BaseModel):
    max_topics: Optional[int] = Field(None, ge=1, le=40)


class RevisionAgentRequest(BaseModel):
    # Dry-run mode: return the plan without touching the schedule.
    apply_actions: bool = True


@router.post("/flashcards/{instance_id}")
def author_flashcards(
    instance_id: int,
    payload: Optional[FlashcardAgentRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Run the retrieval-grounded flashcard authoring agent.

    plan -> retrieve -> author -> critique -> repair -> dedupe -> save
    """
    max_topics = payload.max_topics if payload else None
    try:
        return FlashcardService(db).generate(instance_id, max_topics=max_topics)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/revision-plan/{instance_id}")
def plan_revision(
    instance_id: int,
    payload: Optional[RevisionAgentRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Run the revision planning agent.

    Reads the review log, decides per topic whether to reteach / drill /
    reschedule / promote, and applies the schedule change.
    """
    apply_actions = payload.apply_actions if payload else True
    try:
        return run_revision_agent(db, instance_id, apply_actions=apply_actions)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/recommendations/{instance_id}")
def recommendations(
    instance_id: int,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    """Personalised, evidence-anchored study recommendations."""
    try:
        return run_recommendation_agent(db, instance_id, limit=limit)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
