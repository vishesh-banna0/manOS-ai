"""
File: config.py

Purpose:
Load environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL")

settings = Settings()

print("DATABASE_URL:", settings.DATABASE_URL)