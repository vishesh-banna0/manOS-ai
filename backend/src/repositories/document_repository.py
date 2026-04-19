"""
File: document_repository.py

Purpose:
Handles database operations for Document model.
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.document import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, instance_id: int, file_name: str, file_path: str) -> Document:
        """Create a new document."""
        document = Document(
            instance_id=instance_id,
            file_name=file_name,
            file_path=file_path
        )

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        return document

    def get_by_id(self, document_id: int) -> Optional[Document]:
        """Get document by ID."""
        return self.db.query(Document).filter(Document.id == document_id).first()

    def get_by_instance(self, instance_id: int) -> List[Document]:
        """Get all documents for an instance."""
        return self.db.query(Document).filter(Document.instance_id == instance_id).all()

    def delete(self, document_id: int) -> bool:
        """Delete a document."""
        document = self.get_by_id(document_id)

        if not document:
            return False

        self.db.delete(document)
        self.db.commit()

        return True