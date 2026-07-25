"""
File: faiss_store.py

Purpose:
Persistent, instance-scoped FAISS vector store.

Design notes:
- IndexFlatIP over L2-normalised vectors == exact cosine similarity, so scores
  are interpretable in [-1, 1] rather than unbounded L2 distances.
- IndexIDMap2 keeps FAISS ids aligned with database chunk ids, so a chunk can
  be removed when its document is deleted without rebuilding the whole index.
- Index + metadata persist to data/indexes/{instance_id}/, so restarting the
  API does not throw away the embeddings.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import faiss
import numpy as np

from ...core.config import settings

INDEX_FILE = "index.faiss"
META_FILE = "metadata.json"

# One lock per instance directory: FAISS indexes are not thread-safe for
# concurrent writes, and FastAPI background tasks can overlap.
_locks: Dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(instance_id: int) -> threading.Lock:
    with _locks_guard:
        if instance_id not in _locks:
            _locks[instance_id] = threading.Lock()
        return _locks[instance_id]


class FAISSStore:
    """
    Vector store for one learning instance.

    Metadata records mirror the FAISS ids and carry everything the retriever
    needs to return a grounded citation (text, document, page range).
    """

    def __init__(self, instance_id: int, dim: Optional[int] = None):
        self.instance_id = instance_id
        self.dim = dim or settings.EMBED_DIM
        self.dir: Path = settings.instance_index_dir(instance_id)
        self.index_path = self.dir / INDEX_FILE
        self.meta_path = self.dir / META_FILE

        self.index = self._new_index()
        self.metadata: Dict[int, dict] = {}

        self._load()

    # ------------------------------------------------------------------ setup

    def _new_index(self) -> faiss.Index:
        return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dim))

    def _load(self) -> None:
        if not self.index_path.exists() or not self.meta_path.exists():
            return

        try:
            index = faiss.read_index(str(self.index_path))
            with open(self.meta_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception as exc:  # corrupt index - start clean rather than crash
            print(f"[faiss] failed to load index for instance {self.instance_id}: {exc}")
            self.index = self._new_index()
            self.metadata = {}
            return

        stored_dim = raw.get("dim", self.dim)
        if stored_dim != self.dim:
            print(
                f"[faiss] dim mismatch for instance {self.instance_id} "
                f"(stored {stored_dim}, expected {self.dim}); rebuilding"
            )
            self.index = self._new_index()
            self.metadata = {}
            return

        self.index = index
        self.metadata = {int(key): value for key, value in raw.get("records", {}).items()}

    def save(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        payload = {
            "dim": self.dim,
            "instance_id": self.instance_id,
            "records": {str(key): value for key, value in self.metadata.items()},
        }
        # Write-then-rename so a crash mid-write cannot leave a truncated file.
        tmp = self.meta_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        tmp.replace(self.meta_path)

    # ------------------------------------------------------------------ writes

    def add(
        self,
        ids: Sequence[int],
        embeddings: Sequence[Sequence[float]],
        records: Sequence[dict],
    ) -> int:
        """
        Add or replace vectors by id.

        Returns the number of vectors added.
        """
        if not ids:
            return 0
        if not (len(ids) == len(embeddings) == len(records)):
            raise ValueError("ids, embeddings and records must be the same length")

        vectors = np.asarray(embeddings, dtype="float32")
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        if vectors.shape[1] != self.dim:
            raise ValueError(
                f"embedding dim {vectors.shape[1]} does not match index dim {self.dim}"
            )

        # Normalise defensively - cosine only holds for unit vectors.
        faiss.normalize_L2(vectors)
        id_array = np.asarray(list(ids), dtype="int64")

        with _lock_for(self.instance_id):
            # Replace semantics: drop any existing ids first so re-ingesting a
            # document does not double-count its chunks.
            existing = [i for i in ids if i in self.metadata]
            if existing:
                self.index.remove_ids(np.asarray(existing, dtype="int64"))

            self.index.add_with_ids(vectors, id_array)
            for chunk_id, record in zip(ids, records):
                self.metadata[int(chunk_id)] = record
            self.save()

        return len(ids)

    def remove(self, ids: Sequence[int]) -> int:
        """Remove vectors by id. Returns count removed."""
        present = [int(i) for i in ids if int(i) in self.metadata]
        if not present:
            return 0

        with _lock_for(self.instance_id):
            self.index.remove_ids(np.asarray(present, dtype="int64"))
            for chunk_id in present:
                self.metadata.pop(chunk_id, None)
            self.save()

        return len(present)

    def reset(self) -> None:
        """Drop the whole index for this instance."""
        with _lock_for(self.instance_id):
            self.index = self._new_index()
            self.metadata = {}
            self.save()

    # ----------------------------------------------------------------- queries

    def search(self, query_embedding: Sequence[float], k: int = 5) -> List[dict]:
        """
        Return up to k nearest records, each with a cosine `score`.

        Never raises on an empty index - returns [].
        """
        if self.size == 0:
            return []

        query = np.asarray([query_embedding], dtype="float32")
        if query.shape[1] != self.dim:
            raise ValueError(
                f"query dim {query.shape[1]} does not match index dim {self.dim}"
            )
        faiss.normalize_L2(query)

        k = max(1, min(k, self.size))
        scores, ids = self.index.search(query, k)

        results = []
        for score, chunk_id in zip(scores[0], ids[0]):
            if chunk_id == -1:  # FAISS pads with -1 when fewer than k hits
                continue
            record = self.metadata.get(int(chunk_id))
            if not record:
                continue
            results.append({**record, "chunk_id": int(chunk_id), "score": float(score)})

        return results

    def get_vector(self, chunk_id: int) -> Optional[np.ndarray]:
        """Reconstruct a stored vector (used for MMR diversification)."""
        if int(chunk_id) not in self.metadata:
            return None
        try:
            return self.index.reconstruct(int(chunk_id))
        except RuntimeError:
            return None

    # --------------------------------------------------------------- accessors

    @property
    def size(self) -> int:
        return int(self.index.ntotal)

    def all_records(self) -> List[dict]:
        return [{**record, "chunk_id": key} for key, record in self.metadata.items()]

    def stats(self) -> dict:
        documents = {record.get("document_id") for record in self.metadata.values()}
        return {
            "instance_id": self.instance_id,
            "vectors": self.size,
            "documents_indexed": len({d for d in documents if d is not None}),
            "dim": self.dim,
            "index_path": str(self.index_path),
        }
