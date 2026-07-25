"""
File: config.py

Purpose:
Central configuration loaded from environment variables.

Notes:
- Never print secrets. DATABASE_URL contains credentials.
- All AI model / RAG tuning knobs live here so agents and evaluation
  runs share one source of truth.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root: backend/src/core/config.py -> Manos AI/
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Load .env files by absolute path rather than letting python-dotenv search
# upward from the working directory: the backend can be started from the repo
# root (`uvicorn backend.src.main:app`) or from backend/ (`python main.py`),
# and a CWD-relative search would pick a different file in each case.
# backend/.env wins over a root .env, since that is the documented location.
for _env_file in (BASE_DIR / ".env", BASE_DIR / "backend" / ".env"):
    if _env_file.exists():
        load_dotenv(_env_file, override=True)


def _env(name: str, default: str = "") -> str:
    """Read an env var, tolerating stray whitespace and quotes."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().strip('"').strip("'")


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


class Settings:
    # ----- Database -----
    DATABASE_URL: str = _env(
        "DATABASE_URL",
        "postgresql+pg8000://postgres:1234@localhost:5432/manos_ai",
    )

    # ----- Ollama / LLM -----
    OLLAMA_URL: str = _env("OLLAMA_URL", "http://localhost:11434")

    # Main generation model (authoring, planning, recommendations)
    LLM_MODEL: str = _env("LLM_MODEL", "llama3:8b")

    # Critic model. Kept as a separate knob because self-critique quality is
    # the weakest link in the authoring loop; point this at a stronger model
    # than LLM_MODEL when one is available.
    CRITIC_MODEL: str = _env("CRITIC_MODEL", "qwen2.5:7b")

    EMBED_MODEL: str = _env("EMBED_MODEL", "nomic-embed-text")
    EMBED_DIM: int = _env_int("EMBED_DIM", 768)
    # Inputs per /api/embed request. Batching is what makes ingestion of a
    # full document take seconds instead of minutes.
    EMBED_BATCH_SIZE: int = _env_int("EMBED_BATCH_SIZE", 64)

    LLM_TIMEOUT: int = _env_int("LLM_TIMEOUT", 180)
    LLM_MAX_RETRIES: int = _env_int("LLM_MAX_RETRIES", 2)
    LLM_TEMPERATURE: float = _env_float("LLM_TEMPERATURE", 0.2)
    EMBED_TIMEOUT: int = _env_int("EMBED_TIMEOUT", 60)

    # ----- Chunking -----
    # Semantic chunking merges adjacent sentences while their embeddings stay
    # similar, then splits at the largest distance breakpoints.
    CHUNK_TARGET_WORDS: int = _env_int("CHUNK_TARGET_WORDS", 320)
    CHUNK_MAX_WORDS: int = _env_int("CHUNK_MAX_WORDS", 500)
    CHUNK_MIN_WORDS: int = _env_int("CHUNK_MIN_WORDS", 60)
    CHUNK_BREAKPOINT_PERCENTILE: float = _env_float("CHUNK_BREAKPOINT_PERCENTILE", 82.0)

    # ----- Retrieval -----
    RETRIEVAL_TOP_K: int = _env_int("RETRIEVAL_TOP_K", 5)
    RETRIEVAL_CANDIDATES: int = _env_int("RETRIEVAL_CANDIDATES", 20)
    RETRIEVAL_MMR_LAMBDA: float = _env_float("RETRIEVAL_MMR_LAMBDA", 0.6)
    HYBRID_KEYWORD_WEIGHT: float = _env_float("HYBRID_KEYWORD_WEIGHT", 0.25)

    # ----- Agent budgets -----
    AGENT_MAX_TOPICS: int = _env_int("AGENT_MAX_TOPICS", 12)
    AGENT_CARDS_PER_TOPIC: int = _env_int("AGENT_CARDS_PER_TOPIC", 3)
    AGENT_MAX_REPAIR_ROUNDS: int = _env_int("AGENT_MAX_REPAIR_ROUNDS", 2)
    AGENT_DUPLICATE_THRESHOLD: float = _env_float("AGENT_DUPLICATE_THRESHOLD", 0.88)

    # ----- Uploads -----
    # Textbook PDFs routinely run 30-80 MB, so a 10 MB cap rejects exactly the
    # documents this tool exists to process.
    MAX_UPLOAD_MB: int = _env_int("MAX_UPLOAD_MB", 100)

    # ----- Storage -----
    DATA_DIR: Path = Path(_env("DATA_DIR", str(BASE_DIR / "data")))
    INDEX_DIR: Path = Path(_env("INDEX_DIR", str(BASE_DIR / "data" / "indexes")))

    def instance_index_dir(self, instance_id: int) -> Path:
        path = self.INDEX_DIR / str(instance_id)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
