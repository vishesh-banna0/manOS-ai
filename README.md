# Manos AI

**Manos AI** is a Modular Adaptive Network Orchestrated System for learning: modular (instance-based subjects), adaptive (performance-driven scheduling), network (retrieval-connected knowledge), and OS (agents orchestrating the workflows).

It turns documents into **retrieval-grounded flashcards** and schedules revision with **SM-2 spaced repetition**, driven by **agentic workflows** and measured by a **built-in evaluation harness**.

---

## What it actually does

**1. RAG ingestion pipeline**
PDF/text → extraction (PyMuPDF) → cleaning → **semantic chunking** (sentence embeddings, cut at cosine-distance breakpoints rather than at a fixed word count) → batched embedding generation → **persistent FAISS index**, scoped per learning instance.

**2. Retrieval**
Exact cosine search (`IndexFlatIP` over normalised vectors) blended with lexical overlap, then diversified with **MMR** so one topic does not return five near-identical chunks. Chunks live in Postgres as well as FAISS, so the index can be rebuilt at any time (`POST /ingestion/reindex/{id}`).

**3. Agentic workflows**
Implemented as **state machines with LLM decision points**, not free-form ReAct — local 7–8B models are unreliable at multi-turn tool selection but dependable at schema-constrained single steps. Every LLM call is JSON-validated with retry-on-validation-error.

- **Flashcard authoring agent** — `plan → retrieve → author → critique → repair → semantic dedupe → save`. The planner decides *what deserves a card* instead of emitting 3 per chunk; the critic gates each card on groundedness, self-containment and difficulty honesty; rejected cards loop back to repair with the critic's feedback. Every card stores the chunk ids that grounded it.
- **Revision planning agent** — reads the review log and decides per topic: `reteach` / `drill` / `reschedule` / `promote`, then applies the schedule change. Reteaching authors new remedial cards from retrieved source material.
- **Recommendation agent** — evidence-anchored study advice built from topic accuracy, due backlog, test history and deck-vs-corpus coverage.

**4. Spaced repetition**
Textbook SM-2 as pure, unit-tested functions (`ai/scheduling/sm2.py`), separate from persistence so the evaluation harness can simulate it.

**5. Evaluation harness** (`backend/eval/`)
- **Retrieval** — recall@k, precision@k, MRR, nDCG@k against an auto-built golden set, comparing dense-only vs hybrid vs hybrid+MMR.
- **Generation** — groundedness measured two ways (deterministic lexical overlap + LLM-as-judge), self-containment, semantic duplicate rate, difficulty balance; plus an A/B of the grounded agent against the ungrounded single-chunk baseline.
- **Learning effectiveness** — a synthetic learner with an exponential forgetting curve studies a deck under SM-2 vs the previous scheduler vs review-everything-daily, reporting retention, deck coverage and *recall per review*.

---

## Tech stack

FastAPI · SQLAlchemy · PostgreSQL · FAISS · Ollama (local LLMs) · React/TypeScript · Docker

---

## Setup

**Prerequisites:** Python 3.11+, PostgreSQL, [Ollama](https://ollama.com), Node/Bun for the frontend.

```bash
# 1. Models
ollama pull llama3:8b          # generation
ollama pull qwen2.5:7b         # critic
ollama pull nomic-embed-text   # embeddings

# 2. Database (or use your own Postgres)
docker-compose up -d

# 3. Backend
python -m venv venv && source venv/Scripts/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp backend/.env.example backend/.env                  # then edit DATABASE_URL
python scripts/init_db.py

cd backend && python main.py --reload                 # or see below

# 4. Frontend
cd frontend && bun install && bun run dev
```

Backend at `http://localhost:8000` (docs at `/docs`), frontend at `http://localhost:8080`.

**Running the backend** — either form works, from either directory:

```bash
cd backend && python main.py --reload            # --host / --port / --log-level also accepted
uvicorn backend.src.main:app --reload            # from the repository root
```

`backend/main.py` only puts the repository root on `sys.path` and delegates to uvicorn; the application itself is `backend/src/main.py`.

Check that the AI backends are reachable:

```bash
curl http://localhost:8000/ingestion/status
```

---

## Usage flow

1. **Create an instance** — an isolated subject workspace.
2. **Upload a document** — extracted, semantically chunked and indexed immediately (seconds). Generation is *not* run inline.
3. **Generate flashcards** — runs the authoring agent. Slow by nature: several local LLM calls per topic.
4. **Review** — SM-2 schedules each card; every review is logged.
5. **Test** — adaptive MCQ tests oversample topics you are failing.
6. **Analytics / agents** — accuracy over time, weak areas, coverage, revision plans, recommendations.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `POST/GET/PUT/DELETE` | `/instances` | Instance management |
| `POST` | `/documents/upload/{id}` | Upload → chunk → index |
| `GET/DELETE` | `/documents/...` | List / delete documents |
| `GET` | `/search/{id}?q=` | Hybrid vector + keyword search |
| `POST` | `/search/{id}/answer` | RAG question answering with citations |
| `GET` | `/search/{id}/chunks` | Browse indexed chunks |
| `POST` | `/flashcards/generate/{id}` | Run the authoring agent |
| `GET` | `/flashcards/{id}` | Cards due for review |
| `POST` | `/flashcards/review` | Grade a review (SM-2) |
| `POST` | `/agents/flashcards/{id}` | Authoring agent (full run report) |
| `POST` | `/agents/revision-plan/{id}` | Revision planning agent |
| `GET` | `/agents/recommendations/{id}` | Personalised recommendations |
| `GET` | `/instances/{id}/analytics` | Performance analytics |
| `POST/GET` | `/instances/{id}/tests` | Create / list adaptive tests |
| `POST` | `/tests/{id}/submit` | Grade a test |
| `GET/POST` | `/ingestion/status`, `/ingestion/reindex/{id}` | Health and index maintenance |

---

## Evaluation

```bash
# Offline, no corpus needed - scheduler simulation only
python -m backend.eval.run_eval --suite learning

# Retrieval quality against an auto-built golden set
python -m backend.eval.run_eval --instance 1 --suite retrieval

# Everything (LLM judge makes this slow)
python -m backend.eval.run_eval --instance 1

# Faster: skip LLM-as-judge scoring
python -m backend.eval.run_eval --instance 1 --no-judge
```

Reports are written to `backend/eval/reports/` as JSON and Markdown.

Unit tests:

```bash
pytest backend/tests -q
```

---

## Architecture

```
backend/
  src/
    ai/
      ingestion/     PDF text extraction
      processing/    cleaning, semantic + fixed chunking
      embeddings/    batched Ollama embeddings with caching
      rag/           FAISS store (persistent) + hybrid/MMR retriever
      llm/           JSON-constrained Ollama client + output validators
      agents/        flashcard authoring, revision planning, recommendations
      scheduling/    SM-2 (pure functions)
      qa_generation/ ungrounded baseline, kept for A/B evaluation only
    api/             FastAPI routers
    services/        orchestration
    repositories/    data access
    models/          SQLAlchemy models
    core/            config, database, schema sync
  eval/              retrieval / generation / learning-effectiveness harness
  tests/             unit tests
frontend/            React + TypeScript UI
```

**Design notes**

- *Ingestion is separate from generation.* Upload used to run the LLM once per chunk inside the request handler, so large PDFs timed out. Upload now indexes only; authoring is an explicit call.
- *Embedding is batched.* Ollama's legacy `/api/embeddings` takes one prompt per request; embedding a 40-page PDF that way took ~11 minutes. The batched `/api/embed` endpoint does the same work in ~15 seconds.
- *Dedupe is semantic.* The previous exact-string check let every paraphrase through; card questions are now compared by embedding cosine similarity.
- *The critic is a separate model knob* (`CRITIC_MODEL`). Self-critique is the weakest link in the authoring loop — the evaluation harness reports a **critic vs judge gap** precisely so an over-permissive critic shows up as a number instead of going unnoticed.

---

## Known limitations

- **Critic calibration.** On a 7B critic the in-loop groundedness score runs materially higher than an independent judge's. Treat `critic_groundedness` as optimistic; the harness warns when the gap exceeds 0.25.
- **Generation is slow.** A 4-topic authoring run is roughly 7 minutes on local 7–8B models. It is CPU/GPU-bound in Ollama, not in this code.
- **Small-corpus metrics saturate.** With fewer than ~20 golden queries the retrieval numbers hit 1.0 and stop discriminating; the report flags this.
- **Schema sync is additive only.** `sync_schema()` adds missing columns but never drops or retypes. Use Alembic if you need real migrations.
