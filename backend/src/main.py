"""
File: main.py

Purpose:
Entry point of FastAPI application.
Handles app initialization, middleware, and route registration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.document_routes import router as document_router
from .api.flashcard_routes import router as flashcard_router
from .api.ingestion_routes import router as ingestion_router
from .api.instance_routes import router as instance_router
from .core.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Manos AI backend...")
    create_tables()
    print("Database tables ready")
    yield
    print("Shutting down Manos AI backend...")


app = FastAPI(
    title="Manos AI",
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


@app.get("/")
def root():
    return {"message": "Manos AI Backend Running"}
