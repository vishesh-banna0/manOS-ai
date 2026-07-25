"""
File: search_service.py

Purpose:
Knowledge search over an instance's indexed corpus.

Two surfaces:
- `search`  : ranked chunks with provenance, for the UI and for agents
- `answer`  : RAG question answering - retrieve, then generate an answer that
              cites the retrieved chunks
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..ai.llm.client import LLMUnavailable, generate_text
from ..ai.rag.retriever import get_retriever
from ..core.config import settings
from ..models.chunk import Chunk
from ..models.document import Document


class SearchService:
    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        instance_id: int,
        query: str,
        k: Optional[int] = None,
        use_mmr: bool = True,
    ) -> Dict:
        retriever = get_retriever(instance_id)
        hits = retriever.search(query, k=k or settings.RETRIEVAL_TOP_K, use_mmr=use_mmr)

        return {
            "query": query,
            "instance_id": instance_id,
            "count": len(hits),
            "index_size": retriever.size,
            "results": [self._present(hit) for hit in hits],
        }

    def _present(self, hit: dict) -> dict:
        text = hit.get("text", "")
        return {
            "chunk_id": hit["chunk_id"],
            "title": hit.get("title"),
            "document_id": hit.get("document_id"),
            "document_name": hit.get("document_name"),
            "page_start": hit.get("page_start"),
            "page_end": hit.get("page_end"),
            "score": round(hit.get("score", 0.0), 4),
            "dense_score": round(hit.get("dense_score", 0.0), 4),
            "keyword_score": round(hit.get("keyword_score", 0.0), 4),
            "snippet": text[:400] + ("..." if len(text) > 400 else ""),
            "text": text,
        }

    # ------------------------------------------------------------ RAG answer

    def answer(self, instance_id: int, question: str, k: Optional[int] = None) -> Dict:
        """Retrieve, then answer strictly from the retrieved context."""
        retrieved = self.search(instance_id, question, k=k)
        results = retrieved["results"]

        if not results:
            return {
                "question": question,
                "answer": None,
                "sources": [],
                "warning": (
                    "Nothing indexed for this instance yet, or no chunk matched."
                ),
            }

        context = "\n\n".join(
            f"[{index}] {result['text']}" for index, result in enumerate(results, start=1)
        )

        prompt = f"""Answer the question using ONLY the context below.

CONTEXT:
{context}

QUESTION: {question}

Rules:
- Use only information present in the context.
- Cite the sources you used with their bracket numbers, e.g. [1], [2].
- If the context does not contain the answer, say exactly:
  "The provided material does not answer this question."

ANSWER:"""

        try:
            answer = generate_text(prompt).strip()
        except LLMUnavailable as exc:
            return {
                "question": question,
                "answer": None,
                "sources": results,
                "warning": f"LLM unavailable: {exc}",
            }

        return {
            "question": question,
            "answer": answer,
            "sources": results,
        }

    # ---------------------------------------------------------------- browse

    def list_chunks(self, instance_id: int, limit: int = 50, offset: int = 0) -> Dict:
        query = (
            self.db.query(Chunk, Document.file_name)
            .join(Document, Chunk.document_id == Document.id)
            .filter(Chunk.instance_id == instance_id)
            .order_by(Chunk.document_id, Chunk.position)
        )
        total = query.count()
        rows = query.offset(offset).limit(limit).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "chunks": [
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": file_name,
                    "position": chunk.position,
                    "title": chunk.title,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "word_count": chunk.word_count,
                    "strategy": chunk.strategy,
                    "snippet": chunk.text[:300],
                }
                for chunk, file_name in rows
            ],
        }
