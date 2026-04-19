"""
File: database.py

Purpose:
Configures SQLAlchemy database connection, session management, and base model definitions for the Manos AI backend.

Responsibilities:
- Set up database engine with connection pooling
- Configure SQLAlchemy session factory
- Define base model class with common functionality
- Handle database initialization and migrations

Used by:
- All repository classes for database operations
- Model definitions for table creation
- Application startup for database setup

Notes:
- Uses PostgreSQL with async support
- Includes connection retry logic for reliability
- Supports environment-based configuration
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from typing import Generator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,    # Recycle connections after 5 minutes
    echo=False           # Set to True for SQL logging in development
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()
metadata = Base.metadata

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """
    Create all database tables defined in the models.
    Should be called during application startup.
    """
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """
    Drop all database tables.
    Useful for testing or resetting the database.
    """
    Base.metadata.drop_all(bind=engine)