"""
File: text_chunker.py

Purpose:
Splits extracted text into structured chunks with metadata.
"""

from typing import List, Dict


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100
) -> List[Dict]:
    """
    Split text into overlapping chunks with metadata.

    Args:
        text (str): full extracted text
        chunk_size (int): words per chunk
        overlap (int): overlap between chunks

    Returns:
        List[Dict]: structured chunks
    """

    words = text.split()
    chunks = []

    start = 0
    chunk_id = 1

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]

        chunk_text = " ".join(chunk_words)

        # 👉 Lightweight title (first few words)
        title = " ".join(chunk_words[:8]) if chunk_words else ""

        chunk_data = {
            "chunk_id": chunk_id,
            "text": chunk_text,
            "title": title,
            "word_count": len(chunk_words)
        }

        chunks.append(chunk_data)

        # Move start position (accounting for overlap)
        start = end - overlap
        chunk_id += 1

    return chunks
