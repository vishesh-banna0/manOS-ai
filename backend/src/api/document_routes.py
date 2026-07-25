"""
File: document_routes.py

Purpose:
API endpoints for document upload and management.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..ai.ingestion.pdf_extractor import DocumentExtractionError
from ..core.database import get_db
from ..services.document_service import DocumentService
from ..utils.file_handler import UploadRejected

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload/{instance_id}")
def upload_document(
    instance_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a document: saves, extracts, semantically chunks and indexes it.

    Flashcard authoring is a separate call - running the LLM inline here made
    large PDFs time out.
    """
    try:
        return DocumentService(db).upload_document(instance_id, file)
    except (UploadRejected, DocumentExtractionError) as exc:
        # The file itself is the problem and the message says how to fix it -
        # this is a client error, not a server fault.
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@router.get("/{instance_id}")
def list_documents(instance_id: int, db: Session = Depends(get_db)):
    return DocumentService(db).list_documents(instance_id)


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document along with its chunks and vectors."""
    if not DocumentService(db).delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted"}
