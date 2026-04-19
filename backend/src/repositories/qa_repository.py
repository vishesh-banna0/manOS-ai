"""
File: qa_repository.py

Purpose:
Handles DB operations for Q&A pairs.
"""

from sqlalchemy.orm import Session
from typing import List
from ..models.qa_pair import QAPair


class QARepository:
    def __init__(self, db: Session):
        self.db = db

    def create_many(self, instance_id: int, qa_list: List[dict]) -> List[QAPair]:
        """
        Bulk insert Q&A pairs.
        """

        objects = []

        for qa in qa_list:
            obj = QAPair(
                instance_id=instance_id,
                question=qa.get("question"),
                answer=qa.get("answer"),
                difficulty=qa.get("difficulty"),
                topic=qa.get("topic"),
                source_chunk=qa.get("source_chunk"),
            )
            objects.append(obj)

        self.db.add_all(objects)
        self.db.commit()

        return objects

    def get_by_instance(self, instance_id: int) -> List[QAPair]:
        return self.db.query(QAPair).filter(QAPair.instance_id == instance_id).all()