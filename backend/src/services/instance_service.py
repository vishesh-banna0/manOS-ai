"""
File: instance_service.py

Purpose:
Handles business logic for instance operations.

Responsibilities:
- Coordinate between API and repository
- Validate and process data if needed
- Compute derived fields like documentCount and flashcardsDue

Used by:
- API routes
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from ..repositories.instance_repository import InstanceRepository
from ..schemas.instance import InstanceCreate, InstanceUpdate, InstanceResponse
from ..models.document import Document
from ..models.flashcard import Flashcard
from datetime import datetime


class InstanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InstanceRepository(db)

    def _enrich_instance(self, instance) -> InstanceResponse:
        """Add computed fields to instance response."""
        if not instance:
            return None
        
        # Count documents for this instance
        document_count = self.db.query(func.count(Document.id)).filter(
            Document.instance_id == instance.id
        ).scalar() or 0
        
        # Count flashcards due for review
        flashcards_due = self.db.query(func.count(Flashcard.id)).filter(
            Flashcard.instance_id == instance.id,
            Flashcard.next_review <= datetime.utcnow()
        ).scalar() or 0
        
        return InstanceResponse(
            id=instance.id,
            name=instance.name,
            description=instance.description,
            color=instance.color,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            last_score=instance.last_score,
            document_count=document_count,
            flashcards_due=flashcards_due
        )

    def create_instance(self, data: InstanceCreate) -> InstanceResponse:
        instance = self.repo.create(data)
        return self._enrich_instance(instance)

    def get_instance(self, instance_id: int) -> InstanceResponse:
        instance = self.repo.get_by_id(instance_id)
        return self._enrich_instance(instance)

    def get_all_instances(self, skip: int = 0, limit: int = 100) -> list[InstanceResponse]:
        instances = self.repo.get_all(skip, limit)
        return [self._enrich_instance(inst) for inst in instances]

    def update_instance(self, instance_id: int, data: InstanceUpdate) -> InstanceResponse:
        instance = self.repo.update(instance_id, data)
        return self._enrich_instance(instance)

    def delete_instance(self, instance_id: int) -> bool:
        return self.repo.delete(instance_id)
