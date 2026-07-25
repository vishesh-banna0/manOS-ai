"""
File: ingestion_service.py

Purpose:
The document -> chunks -> embeddings -> index half of the RAG pipeline.

Separated from flashcard generation on purpose: ingestion is fast and
deterministic, generation is slow and model-dependent. Uploading a document
now indexes it immediately and returns; authoring a deck is a separate,
explicitly triggered agent run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..ai.embeddings.embedding_generator import EmbeddingUnavailable, embed_available
from ..ai.ingestion.pdf_extractor import DocumentExtractionError, extract_text_from_pdf
from ..ai.processing.semantic_chunker import semantic_chunk_text
from ..ai.processing.text_cleaner import clean_text
from ..ai.rag.retriever import get_retriever
from ..models.chunk import Chunk
from ..models.document import Document

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst"}


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------ extraction

    def read_document_text(self, file_path: str) -> str:
        """
        Read a document's text.

        Raises:
            DocumentExtractionError: the file cannot yield usable text. The
                message explains why (corrupt, encrypted, scan without OCR).
        """
        path = Path(file_path)

        if not path.exists():
            raise DocumentExtractionError("The uploaded file is no longer on disk.")

        if path.stat().st_size == 0:
            raise DocumentExtractionError(
                "The uploaded file is empty (0 bytes)."
            )

        if path.suffix.lower() == ".pdf":
            return extract_text_from_pdf(str(path))

        if path.suffix.lower() in TEXT_SUFFIXES or not path.suffix:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Salvage what we can rather than failing the whole upload.
                text = path.read_text(encoding="utf-8", errors="replace")

            if not text.strip():
                raise DocumentExtractionError("This file contains no text.")
            return text

        raise DocumentExtractionError(
            f"Unsupported file type: {path.suffix or 'unknown'}"
        )

    # ------------------------------------------------------------- pipeline

    def ingest_document(self, document: Document) -> Dict:
        """
        Chunk, embed and index one document.

        Returns a report describing what happened, including whether the
        vector index was actually updated (it is not, when Ollama is down).

        Raises:
            DocumentExtractionError: the file yields no usable text. The caller
                is expected to surface the message and discard the document.
        """
        report = {
            "document_id": document.id,
            "file_name": document.file_name,
            "chunks_created": 0,
            "vectors_indexed": 0,
            "strategy": None,
            "warnings": [],
        }

        raw_text = self.read_document_text(document.file_path)
        cleaned = clean_text(raw_text)

        if not cleaned.strip():
            raise DocumentExtractionError(
                "The file's text was empty after cleaning - it may contain only "
                "images, symbols or control characters."
            )

        # Re-ingesting the same document should replace its chunks, not
        # duplicate them.
        self._clear_document_chunks(document)

        chunks = semantic_chunk_text(cleaned)
        if not chunks:
            report["warnings"].append("Chunking produced no chunks.")
            return report

        report["strategy"] = chunks[0].get("strategy", "semantic")
        if report["strategy"] == "fixed_fallback":
            report["warnings"].append(
                "Embeddings unavailable - fell back to fixed-size chunking."
            )

        rows: List[Chunk] = []
        for position, chunk in enumerate(chunks):
            rows.append(
                Chunk(
                    instance_id=document.instance_id,
                    document_id=document.id,
                    position=position,
                    text=chunk["text"],
                    title=chunk.get("title", "")[:512],
                    page_start=chunk.get("page_start"),
                    page_end=chunk.get("page_end"),
                    word_count=chunk.get("word_count", 0),
                    strategy=chunk.get("strategy", "semantic"),
                )
            )

        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)

        report["chunks_created"] = len(rows)

        # --- embed + index ---
        indexed, warning = self._index_chunks(document, rows)
        report["vectors_indexed"] = indexed
        if warning:
            report["warnings"].append(warning)

        return report

    def _index_chunks(self, document: Document, rows: List[Chunk]) -> tuple[int, Optional[str]]:
        if not embed_available():
            return 0, (
                "Embedding model unavailable - chunks are stored but not searchable. "
                "Start Ollama and POST /ingestion/reindex/{instance_id}."
            )

        retriever = get_retriever(document.instance_id)
        payload = [
            {
                "id": row.id,
                "text": row.text,
                "title": row.title,
                "document_id": document.id,
                "document_name": document.file_name,
                "page_start": row.page_start,
                "page_end": row.page_end,
                "position": row.position,
            }
            for row in rows
        ]

        try:
            return retriever.index_chunks(payload), None
        except EmbeddingUnavailable as exc:
            return 0, f"Indexing failed: {exc}"

    def _clear_document_chunks(self, document: Document) -> None:
        existing = (
            self.db.query(Chunk).filter(Chunk.document_id == document.id).all()
        )
        if not existing:
            return

        try:
            get_retriever(document.instance_id).remove_document(document.id)
        except Exception as exc:  # index problems must not block re-ingestion
            print(f"[ingestion] could not remove old vectors: {exc}")

        for row in existing:
            self.db.delete(row)
        self.db.commit()

    # -------------------------------------------------------------- reindex

    def reindex_instance(self, instance_id: int) -> Dict:
        """
        Rebuild the vector index for an instance from the chunks table.

        This is the recovery path for a lost/corrupt index or a changed
        embedding model - chunks live in Postgres, so nothing needs re-parsing.
        """
        if not embed_available():
            return {
                "instance_id": instance_id,
                "vectors_indexed": 0,
                "warnings": ["Embedding model unavailable - cannot reindex."],
            }

        chunks = (
            self.db.query(Chunk)
            .filter(Chunk.instance_id == instance_id)
            .order_by(Chunk.document_id, Chunk.position)
            .all()
        )

        documents = {
            document.id: document
            for document in self.db.query(Document).filter(
                Document.instance_id == instance_id
            )
        }

        retriever = get_retriever(instance_id)
        retriever.reset()

        payload = [
            {
                "id": chunk.id,
                "text": chunk.text,
                "title": chunk.title,
                "document_id": chunk.document_id,
                "document_name": getattr(documents.get(chunk.document_id), "file_name", ""),
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "position": chunk.position,
            }
            for chunk in chunks
        ]

        indexed = retriever.index_chunks(payload) if payload else 0

        return {
            "instance_id": instance_id,
            "chunks": len(chunks),
            "vectors_indexed": indexed,
            "warnings": [],
        }

    def status(self, instance_id: int) -> Dict:
        from ..models.chunk import Chunk as ChunkModel

        chunk_count = (
            self.db.query(ChunkModel)
            .filter(ChunkModel.instance_id == instance_id)
            .count()
        )
        document_count = (
            self.db.query(Document).filter(Document.instance_id == instance_id).count()
        )
        retriever = get_retriever(instance_id)

        return {
            "instance_id": instance_id,
            "documents": document_count,
            "chunks": chunk_count,
            "embeddings_available": embed_available(),
            "index": retriever.stats(),
            "index_in_sync": retriever.size == chunk_count,
        }
