"""
File: semantic_chunker.py

Purpose:
Split document text into semantically coherent chunks.

Method (embedding-breakpoint chunking):
1. Split text into sentences, tracking the source page.
2. Embed each sentence.
3. Compute the cosine distance between consecutive sentences.
4. Cut where distance exceeds a percentile threshold - i.e. where the topic
   actually shifts - instead of at an arbitrary word count.
5. Enforce min/max word bounds so no chunk is too small to be useful or too
   large to fit a generation prompt.

Falls back to fixed-size chunking when embeddings are unavailable, so ingestion
still works offline.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import numpy as np

from ...core.config import settings
from ..embeddings.embedding_generator import EmbeddingUnavailable, get_embeddings
from .text_chunker import chunk_text as fixed_size_chunk_text

PAGE_MARKER = re.compile(r"---\s*PAGE\s+(\d+)\s*---")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def _split_sentences_with_pages(text: str) -> List[Dict]:
    """
    Split into sentences while tracking which page each came from.

    The PDF extractor injects "--- PAGE n ---" markers; we consume them for
    metadata rather than letting them pollute chunk text.
    """
    sentences: List[Dict] = []
    current_page = 1
    cursor = 0

    for match in PAGE_MARKER.finditer(text):
        segment = text[cursor:match.start()]
        sentences.extend(_segment_to_sentences(segment, current_page))
        current_page = int(match.group(1))
        cursor = match.end()

    sentences.extend(_segment_to_sentences(text[cursor:], current_page))
    return sentences


def _segment_to_sentences(segment: str, page: int) -> List[Dict]:
    segment = segment.strip()
    if not segment:
        return []

    results = []
    for raw in SENTENCE_SPLIT.split(segment):
        cleaned = " ".join(raw.split()).strip()
        if not cleaned:
            continue
        # Extracted tables/code may contain thousands of words without any
        # punctuation. Split them before embedding to avoid silent truncation.
        words = cleaned.split()
        for start in range(0, len(words), settings.CHUNK_MAX_WORDS):
            part = words[start:start + settings.CHUNK_MAX_WORDS]
            results.append({"text": " ".join(part), "page": page, "words": len(part)})
    return results


def _greedy_pack(sentences: List[Dict], breakpoints: set[int]) -> List[List[Dict]]:
    """
    Group sentences into chunks, cutting at semantic breakpoints while
    respecting CHUNK_MAX_WORDS and merging anything under CHUNK_MIN_WORDS.
    """
    groups: List[List[Dict]] = []
    current: List[Dict] = []
    current_words = 0

    for index, sentence in enumerate(sentences):
        # A single oversized sentence still has to go somewhere.
        would_exceed = current_words + sentence["words"] > settings.CHUNK_MAX_WORDS
        at_breakpoint = index in breakpoints and current_words >= settings.CHUNK_TARGET_WORDS

        if current and (would_exceed or at_breakpoint):
            groups.append(current)
            current = []
            current_words = 0

        current.append(sentence)
        current_words += sentence["words"]

    if current:
        groups.append(current)

    # Merge undersized tails into the previous group.
    merged: List[List[Dict]] = []
    for group in groups:
        words = sum(s["words"] for s in group)
        if (merged and words < settings.CHUNK_MIN_WORDS
                and sum(s["words"] for s in merged[-1]) + words <= settings.CHUNK_MAX_WORDS):
            merged[-1].extend(group)
        else:
            merged.append(group)

    return merged


def _derive_title(text: str) -> str:
    """First clause of the chunk, used as a human-readable label."""
    words = text.split()
    if not words:
        return ""
    return " ".join(words[:10])


def _build_chunk(group: List[Dict], chunk_id: int) -> Dict:
    body = " ".join(sentence["text"] for sentence in group)
    pages = sorted({sentence["page"] for sentence in group})
    return {
        "chunk_id": chunk_id,
        "text": body,
        "title": _derive_title(body),
        "word_count": len(body.split()),
        "page_start": pages[0] if pages else None,
        "page_end": pages[-1] if pages else None,
        "strategy": "semantic",
    }


def semantic_chunk_text(text: str, embeddings: Optional[List[List[float]]] = None) -> List[Dict]:
    """
    Chunk text at semantic boundaries.

    Args:
        text: cleaned document text (may contain PAGE markers)
        embeddings: optional precomputed sentence embeddings (used by tests
                    and the evaluation harness to avoid network calls)

    Returns:
        List of chunk dicts with text, title, word_count and page range.
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences_with_pages(text)
    if not sentences:
        return []

    if sum(s["words"] for s in sentences) <= settings.CHUNK_TARGET_WORDS:
        return [_build_chunk(sentences, 1)]

    if embeddings is None:
        try:
            embeddings = get_embeddings([s["text"] for s in sentences])
        except EmbeddingUnavailable:
            # Offline: fall back to the fixed-size splitter so ingestion still
            # produces usable chunks.
            fallback = fixed_size_chunk_text(text)
            for chunk in fallback:
                chunk["strategy"] = "fixed_fallback"
                chunk.setdefault("page_start", None)
                chunk.setdefault("page_end", None)
            return fallback

    matrix = np.asarray(embeddings, dtype="float32")

    # Cosine distance between consecutive sentences. Vectors arrive normalised,
    # but renormalise defensively so precomputed inputs behave the same.
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = matrix / norms
    similarities = np.sum(unit[:-1] * unit[1:], axis=1)
    distances = 1.0 - similarities

    if distances.size == 0:
        breakpoints: set[int] = set()
    else:
        threshold = float(np.percentile(distances, settings.CHUNK_BREAKPOINT_PERCENTILE))
        # distances[i] is the gap between sentence i and i+1, so a cut lands
        # before sentence i+1.
        breakpoints = {int(i) + 1 for i, d in enumerate(distances) if d >= threshold}

    groups = _greedy_pack(sentences, breakpoints)

    return [_build_chunk(group, index + 1) for index, group in enumerate(groups)]
