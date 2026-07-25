"""
File: init_db.py

Purpose:
Initialize database tables for Manos AI.

Creates any missing tables and adds columns introduced after a table already
existed (see core.database.sync_schema). Safe to re-run.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("Initializing database...")

# Importing core.database registers every model on Base via models/__init__,
# so no model needs to be listed here by hand.
from backend.src.core.database import init_db  # noqa: E402

init_db()

print("Database initialized successfully.")
