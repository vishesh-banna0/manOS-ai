"""
File: embedding_generator.py

Purpose:
Generate embeddings via Ollama with true batching, an in-process cache, and
L2 normalisation so downstream cosine similarity is a plain dot product.

Performance note:
Ollama's legacy /api/embeddings accepts one prompt per request. Embedding a
40-page PDF sentence by sentence that way took ~11 minutes (300 sentences at
~2.2 s each) - per-request overhead dominates, not compute. The newer
/api/embed accepts an array and returns all vectors in one round trip, which
measured ~20x faster on the same corpus. This module prefers /api/embed and
falls back to the legacy endpoint when the server does not support it.

Used by:
- Semantic chunker (sentence-level similarity)
- FAISS store / retriever (indexing + query embedding)
- Agents (semantic dedupe of flashcards)
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Iterable, List, Optional, Sequence

import numpy as np
import requests

from ...core.config import settings

# Ollama truncates silently on very long inputs; cap explicitly so chunk-level
# and sentence-level calls behave predictably.
MAX_INPUT_CHARS = 6000

_cache: OrderedDict[str, List[float]] = OrderedDict()
MAX_CACHE_ENTRIES = 4096
_cache_lock = threading.Lock()

# Set to False after the batch endpoint 404s once, so we stop retrying it.
_batch_endpoint_supported = True


class EmbeddingUnavailable(RuntimeError):
    """Raised when the embedding backend cannot be reached."""


def _cache_key(text: str) -> str:
    return hashlib.sha1(f"{settings.EMBED_MODEL}:{text}".encode("utf-8")).hexdigest()


def _normalize(vector: Sequence[float]) -> List[float]:
    array = np.asarray(vector, dtype="float32")
    norm = float(np.linalg.norm(array))
    if norm > 0:
        return (array / norm).tolist()
    return list(vector)


# ---------------------------------------------------------------- transport


def _post_batch(texts: List[str]) -> Optional[List[List[float]]]:
    """
    Embed a batch through /api/embed.

    Returns None (rather than raising) when the endpoint is unsupported, so
    the caller can fall back to the legacy path.
    """
    global _batch_endpoint_supported

    if not _batch_endpoint_supported:
        return None

    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/embed",
            json={"model": settings.EMBED_MODEL, "input": texts},
            timeout=settings.EMBED_TIMEOUT * 3,  # a batch legitimately takes longer
        )
    except requests.RequestException as exc:
        raise EmbeddingUnavailable(f"Embedding request failed: {exc}") from exc

    if response.status_code == 404:
        _batch_endpoint_supported = False
        return None
    if response.status_code != 200:
        raise EmbeddingUnavailable(
            f"Embedding HTTP {response.status_code}: {response.text[:200]}"
        )

    vectors = response.json().get("embeddings")
    if not vectors or len(vectors) != len(texts):
        raise EmbeddingUnavailable(
            f"Embedding batch returned {len(vectors or [])} vectors for {len(texts)} inputs"
        )

    return vectors


def _post_single(text: str) -> List[float]:
    """Legacy one-prompt-per-request path, with retries."""
    last_error: Optional[Exception] = None

    for _ in range(settings.LLM_MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{settings.OLLAMA_URL}/api/embeddings",
                json={"model": settings.EMBED_MODEL, "prompt": text},
                timeout=settings.EMBED_TIMEOUT,
            )
            if response.status_code != 200:
                last_error = RuntimeError(
                    f"Embedding HTTP {response.status_code}: {response.text[:200]}"
                )
                continue

            vector = response.json().get("embedding")
            if not vector:
                last_error = RuntimeError("Embedding response contained no vector")
                continue

            return vector
        except requests.RequestException as exc:
            last_error = exc

    raise EmbeddingUnavailable(
        f"Embedding failed after {settings.LLM_MAX_RETRIES + 1} attempts: {last_error}"
    )


# ------------------------------------------------------------------- public


def embed_available() -> bool:
    """Cheap health probe so services can degrade gracefully."""
    try:
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            return False
        names = {model.get("name", "") for model in response.json().get("models", [])}
        # Ollama reports "nomic-embed-text:latest" for an unqualified pull.
        wanted = settings.EMBED_MODEL.split(":")[0]
        return any(name.split(":")[0] == wanted for name in names)
    except requests.RequestException:
        return False


def get_embeddings(texts: Sequence[str], normalize: bool = True) -> List[List[float]]:
    """
    Embed a sequence of strings, batching uncached inputs.

    Raises:
        EmbeddingUnavailable: Ollama unreachable or the model is missing.
    """
    prepared = [(text or "").strip()[:MAX_INPUT_CHARS] for text in texts]
    results: List[Optional[List[float]]] = [None] * len(prepared)

    # Resolve from cache first; collect the rest for batching.
    pending_indices: dict[str, List[int]] = {}
    pending_texts: List[str] = []

    with _cache_lock:
        for index, text in enumerate(prepared):
            if not text:
                results[index] = [0.0] * settings.EMBED_DIM
                continue
            cached = _cache.get(_cache_key(text))
            if cached is not None:
                _cache.move_to_end(_cache_key(text))
                results[index] = _normalize(cached) if normalize else list(cached)
            else:
                if text not in pending_indices:
                    pending_texts.append(text)
                    pending_indices[text] = []
                pending_indices[text].append(index)

    batch_size = max(1, settings.EMBED_BATCH_SIZE)
    for start in range(0, len(pending_texts), batch_size):
        batch_texts = pending_texts[start : start + batch_size]

        vectors = _post_batch(batch_texts)
        if vectors is None:  # server lacks /api/embed
            vectors = [_post_single(text) for text in batch_texts]

        for text, vector in zip(batch_texts, vectors):
            final = _normalize(vector) if normalize else list(vector)
            for index in pending_indices[text]:
                results[index] = list(final)
            with _cache_lock:
                # Store raw vectors so normalized and raw callers cannot poison
                # each other's cache entries. Bound sentence-cache memory.
                _cache[_cache_key(text)] = list(vector)
                _cache.move_to_end(_cache_key(text))
                while len(_cache) > MAX_CACHE_ENTRIES:
                    _cache.popitem(last=False)

    return [vector if vector is not None else [0.0] * settings.EMBED_DIM for vector in results]


def get_embedding(text: str, normalize: bool = True) -> List[float]:
    """Embed a single string. Cached by (model, text)."""
    return get_embeddings([text], normalize=normalize)[0]


def to_matrix(vectors: Iterable[Sequence[float]]) -> np.ndarray:
    """Stack vectors into a float32 matrix suitable for FAISS."""
    matrix = np.asarray(list(vectors), dtype="float32")
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    return matrix


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity for normalised or raw vectors."""
    va = np.asarray(a, dtype="float32")
    vb = np.asarray(b, dtype="float32")
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
