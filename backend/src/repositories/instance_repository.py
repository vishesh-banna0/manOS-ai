"""
File: instance_repository.py

Purpose:
Provides database abstraction layer for instance-related CRUD operations.

Responsibilities:
- Create, read, update, delete instances
- Interact with database using SQLAlchemy ORM

Used by:
- Instance service layer

Notes:
- Keeps logic minimal for current development phase
- Avoids over-engineering; extend later when needed
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.document import Document
from ..models.flashcard import Flashcard
from ..models.instance import Instance
from ..models.qa_pair import QAPair
from ..schemas.instance import InstanceCreate, InstanceUpdate


class InstanceRepository:
    def __init__(self, db: Session):
        self.db = db
        print("Instance imported:", Instance)

    def create(self, instance_data: InstanceCreate) -> Instance:
        """Create a new instance."""
        instance = Instance(**instance_data.model_dump())
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def get_by_id(self, instance_id: int) -> Optional[Instance]:
        """Get an instance by ID."""
        return (
            self.db.query(Instance)
            .filter(Instance.id == instance_id)
            .first()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Instance]:
        """Get all instances with pagination."""
        return (
            self.db.query(Instance)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, instance_id: int, update_data: InstanceUpdate) -> Optional[Instance]:
        """Update an instance."""
        instance = self.get_by_id(instance_id)

        if not instance:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            setattr(instance, field, value)

        self.db.commit()
        self.db.refresh(instance)

        return instance

    def delete(self, instance_id: int) -> bool:
        """Delete an instance and all related rows."""
        instance = self.get_by_id(instance_id)

        if not instance:
            return False

        self.db.query(Flashcard).filter(Flashcard.instance_id == instance_id).delete()
        self.db.query(QAPair).filter(QAPair.instance_id == instance_id).delete()
        self.db.query(Document).filter(Document.instance_id == instance_id).delete()
        self.db.delete(instance)
        self.db.commit()

        return True
