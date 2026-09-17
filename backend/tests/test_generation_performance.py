"""Offline regression tests for PDF generation latency and source isolation."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.src.core.database import Base
from backend.src.core.config import settings
from backend.src.models.chunk import Chunk
from backend.src.ai.agents import flashcard_agent as fa
from backend.src.ai.agents import tools as agent_tools
from backend.src.ai.embeddings import embedding_generator as embeddings
from backend.src.ai.processing import semantic_chunker as chunker
from backend.src.ai.rag import retriever
from backend.src.services.flashcard_service import FlashcardService
from backend.src.services.job_service import JobRegistry, JobAlreadyRunning


@pytest.fixture
def isolated_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Chunk(id=1, instance_id=1, document_id=10, text="Neurons use gradients.", title="Neurons"),
            Chunk(id=2, instance_id=1, document_id=20, text="Plants need light.", title="Plants"),
            Chunk(id=3, instance_id=2, document_id=30, text="Other neurons.", title="Other"),
        ])
        db.commit()
        yield db
    engine.dispose()


def test_document_outline_and_readiness_are_scoped(isolated_db):
    tools = agent_tools.AgentTools(isolated_db, 1, document_id=10)
    assert tools.corpus_size() == 1
    assert [c["chunk_id"] for c in tools.corpus_outline()] == [1]
    FlashcardService(isolated_db).assert_ready(1, 10)
    with pytest.raises(ValueError):
        FlashcardService(isolated_db).assert_ready(1, 30)


def test_unindexed_document_uses_scoped_database_evidence(isolated_db):
    tools = agent_tools.AgentTools(isolated_db, 1, document_id=10)
    tools._retriever = SimpleNamespace(search=Mock(return_value=[]))
    assert [c["chunk_id"] for c in tools.search_corpus("neurons")] == [1]
    assert tools.search_corpus("plants") == []


def test_dense_and_keyword_retrieval_do_not_leak_other_documents(monkeypatch):
    records = [
        {"chunk_id": 2, "document_id": 20, "text": "Neurons elsewhere", "score": .99},
        {"chunk_id": 1, "document_id": 10, "text": "Neurons here", "score": .8},
    ]
    searcher = object.__new__(retriever.Retriever)
    searcher.store = SimpleNamespace(size=2, search=Mock(return_value=records), all_records=lambda: records)
    monkeypatch.setattr(retriever, "get_embedding", lambda query: [1., 0.])
    assert [c["chunk_id"] for c in searcher.search("neurons", k=1, document_id=10)] == [1]
    monkeypatch.setattr(retriever, "get_embedding", Mock(side_effect=embeddings.EmbeddingUnavailable("offline")))
    assert [c["chunk_id"] for c in searcher.search("neurons", k=1, document_id=10)] == [1]


def test_dedupe_batches_existing_deck_and_new_cards(monkeypatch):
    embed = Mock(return_value=[[1., 0.], [0., 1.], [1., 0.]])
    monkeypatch.setattr(agent_tools, "get_embeddings", embed)
    tools = agent_tools.AgentTools(None, 1)
    tools.prepare_question_vectors(["old one", "old two", "new paraphrase", "old one"])
    assert tools.is_duplicate("new paraphrase", ["old one", "old two"])[0]
    embed.assert_called_once_with(["old one", "old two", "new paraphrase"])


def test_embedding_outage_is_not_retried_for_every_card(monkeypatch):
    embed = Mock(side_effect=embeddings.EmbeddingUnavailable("offline"))
    monkeypatch.setattr(agent_tools, "get_embeddings", embed)
    tools = agent_tools.AgentTools(None, 1)
    for i in range(20):
        tools.is_duplicate(f"new question {i}", ["previous question"])
    assert embed.call_count == 1


def test_embedding_cache_preserves_normalization_and_deduplicates_batch(monkeypatch):
    embeddings.clear_cache()
    post = Mock(side_effect=lambda texts: [[3., 4.] for _ in texts])
    monkeypatch.setattr(embeddings, "_post_batch", post)
    try:
        assert embeddings.get_embeddings(["same", "same"], normalize=False) == [[3., 4.], [3., 4.]]
        assert embeddings.get_embedding("same") == pytest.approx([.6, .8])
        assert embeddings.get_embedding("same", normalize=False) == [3., 4.]
        post.assert_called_once_with(["same"])
    finally:
        embeddings.clear_cache()


def test_embedding_cache_is_bounded(monkeypatch):
    embeddings.clear_cache()
    monkeypatch.setattr(embeddings, "MAX_CACHE_ENTRIES", 2)
    monkeypatch.setattr(embeddings, "_post_batch", lambda texts: [[1., 0.] for _ in texts])
    try:
        embeddings.get_embeddings(["one", "two", "three"])
        assert len(embeddings._cache) == 2
    finally:
        embeddings.clear_cache()


def test_short_document_skips_sentence_embedding(monkeypatch):
    embed = Mock(side_effect=AssertionError("unnecessary embedding request"))
    monkeypatch.setattr(chunker, "get_embeddings", embed)
    chunks = chunker.semantic_chunk_text("--- PAGE 2 ---\nNeurons learn weights. Gradients update them.")
    assert len(chunks) == 1
    assert chunks[0]["page_start"] == 2
    embed.assert_not_called()


def test_unpunctuated_pdf_content_and_tail_respect_chunk_limit(monkeypatch):
    monkeypatch.setattr(chunker, "get_embeddings", lambda texts: [[1., 0.] for _ in texts])
    text = " ".join(f"word{i}" for i in range(settings.CHUNK_MAX_WORDS * 2 + 10))
    chunks = chunker.semantic_chunk_text(text)
    assert all(c["word_count"] <= settings.CHUNK_MAX_WORDS for c in chunks)
    assert " ".join(c["text"] for c in chunks) == text


def test_overlapping_jobs_rejected_and_key_released_after_completion():
    registry = JobRegistry()
    release = threading.Event()
    entered = threading.Event()
    def target(handle):
        entered.set()
        assert release.wait(2)
        return {"cards_created": 1}
    job = registry.run_in_background("flashcards", target, key="instance:1")
    try:
        assert entered.wait(1)
        with pytest.raises(JobAlreadyRunning):
            registry.run_in_background("flashcards", target, key="instance:1")
    finally:
        worker = next(t for t in threading.enumerate() if t.name.endswith(job.id))
        release.set()
        worker.join(2)
    assert registry.get(job.id).status == "completed"
    new_job = registry.run_in_background("flashcards", lambda handle: {}, key="instance:1")
    assert new_job.id != job.id


def test_planner_provider_failure_stops_without_authoring(monkeypatch):
    agent = fa.FlashcardAgent(None, 1)
    agent.tools = SimpleNamespace(corpus_size=lambda: 1)
    monkeypatch.setattr(agent, "_plan", Mock(side_effect=fa.LLMUnavailable("bad credentials")))
    with pytest.raises(fa.LLMUnavailable, match="bad credentials"):
        agent.run()


@pytest.mark.parametrize("provider,concurrency", [("openrouter", 2), ("ollama", 4)])
def test_topic_workers_preserve_checks_dedupe_and_save_on_owner_thread(monkeypatch, provider, concurrency):
    monkeypatch.setattr(settings, "LLM_PROVIDER", provider)
    monkeypatch.setattr(settings, "LLM_FALLBACK_PROVIDER", "")
    monkeypatch.setattr(settings, "AGENT_TOPIC_CONCURRENCY", concurrency)
    owner = threading.get_ident()
    barrier = threading.Barrier(2) if provider == "openrouter" else None
    saved = []
    def save(cards):
        assert threading.get_ident() == owner
        saved.extend(cards)
        return cards
    tools = SimpleNamespace(
        corpus_size=lambda: 2, existing_questions=lambda: [],
        search_corpus=lambda query: [{"chunk_id": 1 if query == "A" else 2, "text": query}],
        prepare_question_vectors=lambda questions: None,
        is_duplicate=lambda question, against: (question in against, 1., None),
        save_flashcards=save,
    )
    agent = fa.FlashcardAgent(None, 1)
    agent.tools = tools
    monkeypatch.setattr(agent, "_plan", lambda count: [{"topic": "A"}, {"topic": "B"}])
    def author(self, spec, evidence):
        if barrier:
            assert self.db is None
            barrier.wait(timeout=3)
        else:
            assert threading.get_ident() == owner
        return [{"question": "same question", "answer": "answer", "difficulty": "easy"}]
    monkeypatch.setattr(fa.FlashcardAgent, "_author", author)
    monkeypatch.setattr(fa.FlashcardAgent, "_critique", lambda *args: [
        {"index": 0, "verdict": "accept", "groundedness": .9, "feedback": ""}
    ])
    result = agent.run(2)
    assert result.cards_created == 1
    assert result.drafts == 2
    assert result.duplicates == 1
    assert len(saved) == 1
    assert saved[0]["groundedness"] == .9
    assert saved[0]["source_chunk_ids"] in ([1], [2])
    assert result.trace["wall_ms"] >= 0


def test_generation_route_passes_document_scope_and_rejects_bad_input(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.src.api import flashcard_routes as routes

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda: None
    ready = Mock()
    generate = Mock(return_value={"cards_created": 2})
    monkeypatch.setattr(routes.FlashcardService, "assert_ready", ready)
    monkeypatch.setattr(routes.FlashcardService, "generate", generate)
    with TestClient(app) as client:
        response = client.post('/flashcards/generate/1?document_id=10&max_topics=4&wait=true')
        assert response.status_code == 202
        ready.assert_called_once_with(1, 10)
        generate.assert_called_once_with(1, max_topics=4, document_id=10)
        assert client.post('/flashcards/generate/1?document_id=-1').status_code == 422


def test_generation_route_surfaces_overlapping_job_as_conflict(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.src.api import flashcard_routes as routes

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda: None
    monkeypatch.setattr(routes.FlashcardService, "assert_ready", Mock())
    start = Mock(side_effect=JobAlreadyRunning("Already running"))
    monkeypatch.setattr(routes.jobs, "run_in_background", start)
    with TestClient(app) as client:
        response = client.post('/flashcards/generate/1?document_id=10')
    assert response.status_code == 409
    assert response.json()["detail"] == "Already running"
    assert start.call_args.kwargs["key"] == "flashcards:1"
