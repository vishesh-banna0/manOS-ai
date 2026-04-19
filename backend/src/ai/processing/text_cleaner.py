"""
File: text_cleaner.py

Purpose:
Minimal cleaning for stable downstream processing.
"""

import re


def clean_text(text: str) -> str:
    """
    Perform minimal cleaning.
    DO NOT over-clean.
    """

    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)

    # Remove weird non-printable characters
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)

    return text.strip()