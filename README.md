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

FastAPI · SQLAlchemy · PostgreSQL · FAISS · OpenRouter (hosted LLMs) · Ollama (embeddings, optional local LLMs) · React/TypeScript · Docker

---

## Setup

**Prerequisites:** Python 3.11+, PostgreSQL, [Ollama](https://ollama.com), Node/Bun for the frontend.

Generation runs on **OpenRouter** by default (`LLM_PROVIDER=openrouter`), using
`nvidia/nemotron-3-super-120b-a12b:free`. Ollama is still required either way -
embeddings have no OpenRouter equivalent, so ingestion and semantic dedupe
always run locally.

```bash
# 1. Models
ollama pull nomic-embed-text   # embeddings - always needed

# Only if you set LLM_PROVIDER=ollama (or use it as a fallback):
ollama pull llama3:8b          # generation
ollama pull qwen2.5:7b         # critic

# 2. Database (or use your own Postgres)
docker-compose up -d

# 3. Backend
python -m venv venv && source venv/Scripts/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp backend/.env.example backend/.env                  # then set DATABASE_URL + OPENROUTER_API_KEY
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
3. **Generate flashcards** - choose a 4-, 8-, or 12-topic deck. Cards are grounded, reviewed and saved as each topic completes.
4. **Review** — SM-2 schedules each card; every review is logged.
5. **Test** — adaptive MCQ tests oversample topics you are failing.
6. **Analytics / agents** — accuracy over time, weak areas, coverage, revision plans, recommendations.

---

## Generation performance

The upload and flashcard screens offer **Starter (4 topics)**, **Standard (8)**,
and **Detailed (12)** decks. Starter is the UI default and reduces the amount of
work; authoring, source retrieval, critique, repair and duplicate checks still
run. With no repairs/retries, four topics require 9 model calls versus 25 for
twelve topics. The API retains `AGENT_MAX_TOPICS` when `max_topics` is omitted.

An upload's Generate button now targets that document using `document_id`;
generation from the Flashcards page covers the whole workspace. Outline and
retrieval both respect the selected document. Overlapping background generation
jobs in one workspace return HTTP 409. Failed generation can be retried without
uploading the document again, and temporary polling failures are retried without
starting another job.

Question embeddings are batched before semantic deduplication, repeated inputs
are embedded once per batch, and the shared embedding cache is bounded. Short
documents that fit in one chunk skip sentence-level embeddings. Oversized PDF
sentences/tables are split before embedding, retaining their text and page range.
Multiple files selected together are uploaded/indexed sequentially to avoid
competing for the local embedding model.

Local verification with `nomic-embed-text`: embedding 24 distinct synthetic
questions took a median **50.978 seconds** as individual requests versus
**2.559 seconds** in one batch (three trials each, alternating order, model
warmed up and in-process cache cleared before every trial). This measures the
embedding step, **not** end-to-end PDF generation or hosted model latency.

Hosted topic authoring can overlap with `AGENT_TOPIC_CONCURRENCY` (1–4). The
default is 1 for free hosted tiers and 2 for other hosted models; Ollama and
configurations with an Ollama fallback always stay sequential. Workers only run
model calls; database access, deduplication and saving stay on the owner thread.
Each report includes `trace.wall_ms` as well as cumulative model-call time.
Latency still depends on document size, provider availability and model speed.

The frontend loads upload, flashcard, test and analytics pages on demand, keeping
the chart bundle out of the initial download. Set `VITE_API_URL` when the backend
is not at `http://localhost:8000`.

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
- *The provider is one switch.* `LLM_PROVIDER=openrouter|ollama` is read only by
  `ai/llm/client._raw_generate()`. Retries, JSON extraction, validation and
  tracing sit above it, so the agents never branch on provider, and
  `LLM_FALLBACK_PROVIDER=ollama` retries a transient hosted failure locally.
- *The critic is a separate model knob* (`CRITIC_MODEL`, or
  `OPENROUTER_CRITIC_MODEL`; on OpenRouter it defaults to the same model). Self-critique is the weakest link in the authoring loop — the evaluation harness reports a **critic vs judge gap** precisely so an over-permissive critic shows up as a number instead of going unnoticed.

---

## Known limitations

- **Critic calibration.** On a 7B critic the in-loop groundedness score runs materially higher than an independent judge's. Treat `critic_groundedness` as optimistic; the harness warns when the gap exceeds 0.25.
- **Model latency.** Generation still requires author and critic calls per topic, with additional calls for repairs. Starter decks reduce coverage and runtime; concurrency helps hosted providers only when their rate limits allow it. End-to-end timing depends on the PDF and model.
- **Small-corpus metrics saturate.** With fewer than ~20 golden queries the retrieval numbers hit 1.0 and stop discriminating; the report flags this.
- **Schema sync is additive only.** `sync_schema()` adds missing columns but never drops or retypes. Use Alembic if you need real migrations.
