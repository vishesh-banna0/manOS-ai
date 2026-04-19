"""
File: text_cleaner.py

Purpose:
Clean and standardize extracted text.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean extracted text.

    Removes:
    - Extra whitespace
    - Special characters (but keeps periods, commas)
    - Page separators
    - Empty lines

    Args:
        text (str): Raw extracted text

    Returns:
        str: Cleaned text
    """

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove page separators
    text = re.sub(r'--- PAGE \d+ ---', '', text)

    # Remove URLs
    text = re.sub(r'http\S+|www\S+', '', text)

    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)

    # Remove special characters but keep punctuation
    text = re.sub(r'[^a-zA-Z0-9\s\.\,\!\?\'\"\-\:]', '', text)

    # Remove extra spaces again
    text = re.sub(r'\s+', ' ', text).strip()

    return text
