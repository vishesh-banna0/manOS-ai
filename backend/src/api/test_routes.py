"""
File: test_routes.py

Purpose:
Adaptive test endpoints.

Paths match what the frontend already calls:
  POST /instances/{id}/tests   -> create a session
  POST /tests/{id}/submit      -> grade a submission
"""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services.test_service import TestService

router = APIRouter(tags=["Tests"])


class CreateTestRequest(BaseModel):
    count: int = Field(10, ge=1, le=50)


class SubmitTestRequest(BaseModel):
    # question id (or position) -> selected option index
    answers: Dict[str, int] = Field(default_factory=dict)


@router.post("/instances/{instance_id}/tests")
def create_test(
    instance_id: int,
    payload: CreateTestRequest = CreateTestRequest(),
    db: Session = Depends(get_db),
):
    """Generate an adaptive test weighted toward weak topics."""
    try:
        return TestService(db).create_test(instance_id, count=payload.count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/instances/{instance_id}/tests")
def list_tests(instance_id: int, db: Session = Depends(get_db)):
    return TestService(db).list_tests(instance_id)


@router.get("/tests/{test_id}")
def get_test(test_id: int, include_answers: bool = False, db: Session = Depends(get_db)):
    result = TestService(db).get_test(test_id, include_answers=include_answers)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    return result


@router.post("/tests/{test_id}/submit")
def submit_test(test_id: int, payload: SubmitTestRequest, db: Session = Depends(get_db)):
    """Grade a submission and record the score against the instance."""
    result = TestService(db).submit_test(test_id, payload.answers)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    return result
