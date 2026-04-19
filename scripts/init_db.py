"""
File: init_db.py

Purpose:
Initialize database tables for Manos AI.
"""

import sys
import os

# Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("Initializing Database...")

from backend.src.core.database import engine, Base

# IMPORTANT: import all models so SQLAlchemy registers them
from backend.src.models.instance import Instance
from backend.src.models.document import Document
from backend.src.models.qa_pair import QAPair
# add more models later if needed

print("Creating tables...")

Base.metadata.create_all(bind=engine)

print("Database initialized successfully!")