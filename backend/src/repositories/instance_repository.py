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

import shutil
from typing import List, Optional

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.chunk import Chunk
from ..models.document import Document
from ..models.flashcard import Flashcard
from ..models.instance import Instance
from ..models.qa_pair import QAPair
from ..models.review_log import ReviewLog
from ..models.test import Test, TestQuestion
from ..schemas.instance import InstanceCreate, InstanceUpdate


class InstanceRepository:
    def __init__(self, db: Session):
        self.db = db

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
        """
        Delete an instance and everything derived from it.

        This includes the on-disk FAISS index and uploaded files: leaving them
        behind leaks storage, and worse, a future instance that reuses the id
        would inherit stale vectors.
        """
        instance = self.get_by_id(instance_id)

        if not instance:
            return False

        # Review logs and test questions reference flashcards/tests, so they
        # have to go first or the deletes below hit FK constraints.
        self.db.query(ReviewLog).filter(ReviewLog.instance_id == instance_id).delete()

        test_ids = [
            row[0]
            for row in self.db.query(Test.id).filter(Test.instance_id == instance_id).all()
        ]
        if test_ids:
            self.db.query(TestQuestion).filter(
                TestQuestion.test_id.in_(test_ids)
            ).delete(synchronize_session=False)
            self.db.query(Test).filter(Test.instance_id == instance_id).delete()

        self.db.query(Flashcard).filter(Flashcard.instance_id == instance_id).delete()
        self.db.query(QAPair).filter(QAPair.instance_id == instance_id).delete()
        self.db.query(Chunk).filter(Chunk.instance_id == instance_id).delete()
        self.db.query(Document).filter(Document.instance_id == instance_id).delete()
        self.db.delete(instance)
        self.db.commit()

        self._delete_storage(instance_id)

        return True

    @staticmethod
    def _delete_storage(instance_id: int) -> None:
        """Remove the vector index and uploaded files for a deleted instance."""
        from ..ai.rag.retriever import invalidate_retriever

        invalidate_retriever(instance_id)

        for path in (
            settings.INDEX_DIR / str(instance_id),
            settings.DATA_DIR / "instances" / str(instance_id),
        ):
            try:
                if path.exists():
                    shutil.rmtree(path)
            except OSError as exc:
                print(f"[instances] could not remove {path}: {exc}")
