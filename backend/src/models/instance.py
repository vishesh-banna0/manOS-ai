"""
File: instance.py

Purpose:
Defines the SQLAlchemy database model for learning instances, representing isolated subject workspaces with metadata and relationships to documents, questions, flashcards, and tests.

Responsibilities:
- Define database table structure for instances
- Establish relationships with related entities (documents, flashcards, tests)
- Include metadata fields like name, description, creation date
- Support instance-based data isolation constraints

Used by:
- Repositories for database operations on instances
- Services for business logic involving instance data
- Schemas for validation and serialization

Notes:
- Uses PostgreSQL with potential for vector extensions
- Instance ID serves as foreign key in related tables for isolation
- Includes performance tracking fields like last_score
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, func
from ..core.database import Base

class Instance(Base):
    __tablename__ = "instances"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code like #FF5733
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_score = Column(Float, nullable=True)  # Performance tracking

    def __repr__(self):
        return f"<Instance(id={self.id}, name='{self.name}')>"