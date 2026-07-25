"""
File: document_service.py

Purpose:
Document upload and its ingestion side effects.

Behaviour change: upload no longer runs LLM generation inline. It used to call
the model once per chunk inside the request handler, so a 40-page PDF held the
HTTP connection open for minutes and usually timed out. Upload now extracts,
chunks and indexes (fast, deterministic), then returns. Authoring a deck is a
separate call to the flashcard agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..models.chunk import Chunk
from ..models.document import Document
from ..repositories.document_repository import DocumentRepository
from ..utils.file_handler import save_file
from .ingestion_service import IngestionService


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        self.ingestion = IngestionService(db)

    def upload_document(self, instance_id: int, file: UploadFile) -> Dict:
        """
        Save, extract, chunk and index a document.

        Raises:
            UploadRejected: the file is empty, too large or an unsupported type.
            DocumentExtractionError: the file yields no usable text.

        Both are reported to the client as 400 with the underlying message; a
        rejected upload leaves no document row and no file on disk, so the user
        can simply fix the file and retry.
        """
        # Validated before anything is persisted - an empty or oversized file
        # should never become a Document row.
        file_path = save_file(instance_id, file)
        file_name = Path(file_path).name

        # save_file overwrites the blob at the same path, so re-uploading a
        # filename must replace the previous document rather than add a second
        # one. Otherwise both rows point at the same file and the corpus ends
        # up with two identical copies of every chunk, which then produces
        # duplicate flashcards.
        self._replace_existing(instance_id, file_name)

        document = self.repo.create(
            instance_id=instance_id,
            file_name=file_name,
            file_path=file_path,
        )

        try:
            report = self.ingestion.ingest_document(document)
        except Exception:
            # Ingestion failed after the document row was committed. Remove the
            # row and the saved blob so a retry does not accumulate orphan
            # documents that inflate the dashboard count and are never chunked.
            self.db.rollback()
            self._discard(document)
            raise

        chunks = report["chunks_created"]
        vectors = report["vectors_indexed"]

        if vectors == 0:
            message = f"Document uploaded and split into {chunks} chunks, but not indexed."
        else:
            message = (
                f"Document processed: {chunks} semantic chunks, {vectors} vectors "
                f"indexed. Generate flashcards to build a deck."
            )

        response = {
            "message": message,
            "document": self._present(document),
            "stats": {
                "chunks": chunks,
                "vectors_indexed": vectors,
                "strategy": report["strategy"],
            },
        }

        if report["warnings"]:
            response["warning"] = " ".join(report["warnings"])

        return response

    def list_documents(self, instance_id: int) -> List[Dict]:
        return [self._present(document) for document in self.repo.get_by_instance(instance_id)]

    def delete_document(self, document_id: int) -> bool:
        """Delete a document along with its chunks and vectors."""
        document = self.repo.get_by_id(document_id)
        if not document:
            return False

        from ..ai.rag.retriever import get_retriever

        try:
            get_retriever(document.instance_id).remove_document(document.id)
        except Exception as exc:  # never block deletion on index problems
            print(f"[documents] could not remove vectors for {document_id}: {exc}")

        self.db.query(Chunk).filter(Chunk.document_id == document_id).delete()
        self.db.delete(document)
        self.db.commit()
        return True

    def _replace_existing(self, instance_id: int, file_name: str) -> None:
        """Drop earlier documents with this filename, plus their chunks/vectors."""
        previous = (
            self.db.query(Document)
            .filter(Document.instance_id == instance_id, Document.file_name == file_name)
            .all()
        )
        if not previous:
            return

        from ..ai.rag.retriever import get_retriever

        retriever = None
        try:
            retriever = get_retriever(instance_id)
        except Exception as exc:
            print(f"[documents] could not open index for {instance_id}: {exc}")

        for document in previous:
            if retriever is not None:
                try:
                    retriever.remove_document(document.id)
                except Exception as exc:
                    print(f"[documents] could not remove vectors for {document.id}: {exc}")
            self.db.query(Chunk).filter(Chunk.document_id == document.id).delete()
            self.db.delete(document)

        self.db.commit()
        print(
            f"[documents] replaced {len(previous)} earlier copy/copies of "
            f"'{file_name}' in instance {instance_id}"
        )

    def _discard(self, document: Document) -> None:
        """Best-effort cleanup of a partially ingested document, row and file."""
        file_path = document.file_path

        try:
            self.db.query(Chunk).filter(Chunk.document_id == document.id).delete()
            self.db.delete(document)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            print(f"[documents] could not roll back document {document.id}: {exc}")

        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError as exc:
            print(f"[documents] could not remove {file_path}: {exc}")

    def _present(self, document: Document) -> Dict:
        chunk_count = self.db.query(Chunk).filter(Chunk.document_id == document.id).count()
        return {
            "id": document.id,
            "instance_id": document.instance_id,
            "file_name": document.file_name,
            "chunks": chunk_count,
            "created_at": document.created_at.isoformat() if document.created_at else None,
        }
