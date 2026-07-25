"""
File: analytics_routes.py

Purpose:
Performance analytics for an instance.

Backs GET /instances/{id}/analytics, which the Analytics page called long
before it existed on the server.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.instance import Instance
from ..services.analytics_service import AnalyticsService

router = APIRouter(prefix="/instances", tags=["Analytics"])


@router.get("/{instance_id}/analytics")
def get_analytics(
    instance_id: int,
    days: int = Query(30, ge=1, le=365, description="Look-back window"),
    db: Session = Depends(get_db),
):
    exists = db.query(Instance.id).filter(Instance.id == instance_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Instance not found")

    return AnalyticsService(db).get_analytics(instance_id, days=days)
