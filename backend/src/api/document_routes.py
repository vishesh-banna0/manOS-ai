"""
File: document_routes.py

Purpose:
API endpoints for document upload.
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload/{instance_id}")
def upload_document(
    instance_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        service = DocumentService(db)
        return service.upload_document(instance_id, file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
