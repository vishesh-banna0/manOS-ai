"""
File: chunk.py

Purpose:
Persisted semantic chunks produced during ingestion.

Why chunks live in the database as well as FAISS:
- The FAISS index can be rebuilt from these rows if it is lost or the
  embedding model changes.
- Retrieval results cite chunk ids; joining back to this table gives the
  document name and page range for provenance in the UI.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)

    instance_id = Column(
        Integer, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Order of the chunk within its source document.
    position = Column(Integer, nullable=False, default=0)

    text = Column(Text, nullable=False)
    title = Column(String(512), nullable=True)

    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=False, default=0)

    # "semantic" or "fixed_fallback" - lets the eval harness compare strategies.
    strategy = Column(String(32), nullable=False, default="semantic")

    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", backref="chunks")

    def __repr__(self):
        return f"<Chunk(id={self.id}, doc={self.document_id}, words={self.word_count})>"
