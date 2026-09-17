"""
File: ingestion_routes.py

Purpose:
Ingestion status and index maintenance.

Previously a single stub returning {"status": "ready"} regardless of state.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.embeddings.embedding_generator import embed_available
from ..ai.llm.client import available as llm_available, list_models
from ..core.config import settings
from ..core.database import get_db
from ..services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.get("/status")
def service_status():
    """Health of the AI backends the pipeline depends on."""
    embeddings_ok = embed_available()
    llm_ok = llm_available(settings.LLM_MODEL)
    critic_ok = llm_available(settings.CRITIC_MODEL)

    return {
        "status": "ready" if (embeddings_ok and llm_ok) else "degraded",
        "llm_provider": settings.LLM_PROVIDER,
        "fallback_provider": settings.LLM_FALLBACK_PROVIDER or None,
        # Whether a key is configured, never the key itself.
        "api_key_configured": bool(settings.OPENROUTER_API_KEY),
        # Embeddings always run on Ollama - OpenRouter has no embeddings API.
        "ollama_url": settings.OLLAMA_URL,
        "models": {
            "embedding": {"name": settings.EMBED_MODEL, "available": embeddings_ok},
            "generation": {"name": settings.LLM_MODEL, "available": llm_ok},
            "critic": {"name": settings.CRITIC_MODEL, "available": critic_ok},
        },
        "installed_models": list_models(),
    }


@router.get("/status/{instance_id}")
def instance_status(instance_id: int, db: Session = Depends(get_db)):
    """Chunk/vector counts for one instance, and whether they agree."""
    return IngestionService(db).status(instance_id)


@router.post("/reindex/{instance_id}")
def reindex(instance_id: int, db: Session = Depends(get_db)):
    """
    Rebuild the vector index from stored chunks.

    Use after the embedding model changes, or if the index is lost - chunks
    live in Postgres, so nothing needs re-parsing.
    """
    result = IngestionService(db).reindex_instance(instance_id)
    if result["warnings"]:
        raise HTTPException(status_code=503, detail=" ".join(result["warnings"]))
    return result
