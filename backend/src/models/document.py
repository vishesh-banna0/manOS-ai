"""
File: document.py

Purpose:
Defines the Document model representing uploaded files (PDF/text)
associated with a learning instance.

Responsibilities:
- Store file metadata
- Link documents to instances
- Enable future processing (text extraction, chunking)

Used by:
- Ingestion system
- Document repository/service
"""

"""
File: document.py

Purpose:
Defines Document model linked to Instance.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key → Instance
    instance_id = Column(Integer, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)

    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    instance = relationship("Instance", backref="documents")