"""
File: instance.py

Purpose:
Defines Pydantic validation schemas for instance-related API requests and responses, ensuring data integrity and type safety in the API layer.

Responsibilities:
- Define input schemas for instance creation and updates
- Define output schemas for instance data serialization
- Include validation rules for required fields and data types
- Support nested schemas for related entities

Used by:
- API routes for request/response handling
- Services for data validation before processing
- Frontend for type-safe API interactions

Notes:
- Uses Pydantic v2 for modern validation features
- Includes optional fields for partial updates
- Supports instance metadata like color and description
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class InstanceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Instance name")
    description: Optional[str] = Field(None, description="Instance description")
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$|^hsl\(\d+,\s*\d+%,\s*\d+%\)$", description="Hex or HSL color code")

class InstanceCreate(InstanceBase):
    pass

class InstanceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$|^hsl\(\d+,\s*\d+%,\s*\d+%\)$")

class InstanceResponse(InstanceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    last_score: Optional[float] = None
    document_count: int = 0
    flashcards_due: int = 0

    class Config:
        from_attributes = True
        populate_by_name = True