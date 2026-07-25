"""
File: job_routes.py

Purpose:
Poll the status of long-running background jobs.

Flashcard authoring runs for minutes; the client starts a job, then polls here
to show which stage it is on and how many cards exist so far.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.job_service import jobs

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("")
def list_jobs(kind: Optional[str] = Query(None, description="Filter by job kind")):
    return jobs.list(kind=kind)


@router.get("/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Unknown job id. Finished jobs are kept for 30 minutes.",
        )
    return job.to_dict()
