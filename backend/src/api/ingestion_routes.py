"""
File: ingestion_routes.py

Purpose:
API endpoints for document ingestion and processing.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.get("/status")
def ingestion_status():
    """Check ingestion service status."""
    return {"status": "ready"}
