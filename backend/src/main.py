"""
File: main.py

Purpose:
Entry point of the FastAPI application.
Handles app initialization, middleware, and route registration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .ai.embeddings.embedding_generator import embed_available
from .ai.llm.client import available as llm_available
from .api.agent_routes import router as agent_router
from .api.analytics_routes import router as analytics_router
from .api.document_routes import router as document_router
from .api.flashcard_routes import router as flashcard_router
from .api.ingestion_routes import router as ingestion_router
from .api.instance_routes import router as instance_router
from .api.job_routes import router as job_router
from .api.search_routes import router as search_router
from .api.test_routes import router as test_router
from .core.config import settings
from .core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Manos AI backend...")
    init_db()
    print("Database ready")

    # Report AI backend health at boot rather than failing mysteriously on the
    # first request.
    if not llm_available(settings.LLM_MODEL):
        print(
            f"  WARNING: generation model '{settings.LLM_MODEL}' unavailable at "
            f"{settings.OLLAMA_URL}. Agents will use fallbacks."
        )
    if not embed_available():
        print(
            f"  WARNING: embedding model '{settings.EMBED_MODEL}' unavailable. "
            f"Retrieval is disabled until it is pulled."
        )

    yield
    print("Shutting down Manos AI backend...")


app = FastAPI(
    title="Manos AI",
    description=(
        "Adaptive learning system: retrieval-grounded flashcards, agentic "
        "generation and revision planning, spaced repetition."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(instance_router)
app.include_router(document_router)
app.include_router(flashcard_router)
app.include_router(ingestion_router)
app.include_router(search_router)
app.include_router(agent_router)
app.include_router(analytics_router)
app.include_router(test_router)
app.include_router(job_router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "Manos AI Backend Running", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "llm": llm_available(settings.LLM_MODEL),
        "embeddings": embed_available(),
    }
