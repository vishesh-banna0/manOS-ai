"""
File: text_cleaner.py

Purpose:
Minimal cleaning for stable downstream processing.
"""

import re

# Control characters that must go. Note the previous filter was
# `[^\x00-\x7F]`, which strips everything ABOVE 0x7F and therefore kept NUL
# and the other C0 controls that PDFs embed around glyphs and ligatures.
# Postgres rejects 0x00 in text columns outright ("invalid byte sequence for
# encoding UTF8"), so a real PDF would fail on insert.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NON_ASCII = re.compile(r"[^\x00-\x7F]+")
WHITESPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """
    Perform minimal cleaning.
    DO NOT over-clean.
    """
    if not text:
        return ""

    # Drop control characters first (keeps \t, \n, \r for the whitespace pass).
    text = CONTROL_CHARS.sub(" ", text)

    # Replace non-ASCII runs.
    text = NON_ASCII.sub(" ", text)

    # Normalize whitespace last.
    text = WHITESPACE.sub(" ", text)

    return text.strip()
