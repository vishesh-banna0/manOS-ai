"""
Unit tests for the provider-agnostic LLM client.

Every test mocks the HTTP layer - nothing here makes a real OpenRouter or
Ollama request, so the suite runs offline and costs nothing. The real API key
is never used: settings.OPENROUTER_API_KEY is monkeypatched to a dummy.
"""

import json

import pytest
import requests

from backend.src.ai.llm import client
from backend.src.ai.llm import schemas
from backend.src.core.config import settings

# `json` is shadowed by the requests kwarg inside the fake_post helpers.
dumps = json.dumps

DUMMY_KEY = "sk-or-v1-test-key-not-real"
VALID_CARDS = {
    "cards": [
        {
            "question": "What does SM-2 adjust after a review?",
            "answer": "It adjusts the ease factor and the next interval.",
            "difficulty": "medium",
            "evidence": "SM-2 updates the ease factor and interval.",
        }
    ]
}


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, payload=None, text=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


def chat_response(content):
    """An OpenRouter chat-completions envelope carrying `content`."""
    return FakeResponse(
        200, {"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


@pytest.fixture(autouse=True)
def openrouter_env(monkeypatch):
    """Deterministic provider config, a dummy key, and no real sleeping."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "LLM_FALLBACK_PROVIDER", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", DUMMY_KEY)
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
    monkeypatch.setattr(settings, "LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
    monkeypatch.setattr(settings, "CRITIC_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "LLM_BACKOFF_BASE", 1.0)
    monkeypatch.setattr(settings, "LLM_BACKOFF_MAX", 30.0)
    client._no_json_mode.clear()
    yield
    client._no_json_mode.clear()


@pytest.fixture
def no_sleep(monkeypatch):
    """Record backoff delays instead of actually waiting."""
    delays = []
    monkeypatch.setattr(client.time, "sleep", lambda seconds: delays.append(seconds))
    return delays


# ------------------------------------------------------- successful generation


def test_openrouter_generation_returns_validated_cards(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["headers"] = headers
        return chat_response(dumps(VALID_CARDS))

    monkeypatch.setattr(requests, "post", fake_post)

    cards = client.generate_json("write a card", schemas.validate_cards, node="author")

    assert cards[0]["question"] == "What does SM-2 adjust after a review?"
    assert cards[0]["difficulty"] == "medium"
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["model"] == "nvidia/nemotron-3-super-120b-a12b:free"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["headers"]["Authorization"] == f"Bearer {DUMMY_KEY}"


def test_each_agent_gets_its_own_system_prompt(monkeypatch):
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen[json["messages"][0]["content"][:40]] = True
        return chat_response(dumps(VALID_CARDS))

    monkeypatch.setattr(requests, "post", fake_post)

    for node in ("author", "critic", "repair"):
        try:
            client.generate_json("x", schemas.validate_cards, node=node)
        except Exception:
            pass

    # Three distinct system prompts were sent, one per agent role.
    assert len(seen) == 3
    prompts = {n: client.system_prompt_for(n) for n in ("planner", "author", "critic", "repair")}
    assert len(set(prompts.values())) == 4
    assert "ONLY the retrieved context" in prompts["author"]
    assert "unsupported" in prompts["critic"]
    assert "unsupported" in prompts["repair"]


def test_trace_records_provider_attempts_and_latency(monkeypatch):
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: chat_response(dumps(VALID_CARDS))
    )
    trace = client.LLMTrace()

    client.generate_json("x", schemas.validate_cards, node="author", trace=trace)

    call = trace.calls[0]
    assert call.ok and call.node == "author" and call.provider == "openrouter"
    assert call.attempts == 1
    assert trace.summary()["llm_calls"] == 1


# ------------------------------------------------------- malformed / invalid


def test_malformed_json_recovers_on_retry(monkeypatch):
    responses = [
        chat_response("Sure! Here are your flashcards, hope they help."),
        chat_response(dumps(VALID_CARDS)),
    ]
    monkeypatch.setattr(requests, "post", lambda *a, **k: responses.pop(0))
    trace = client.LLMTrace()

    cards = client.generate_json("x", schemas.validate_cards, node="author", trace=trace)

    assert len(cards) == 1
    assert trace.calls[0].attempts == 2  # recovered on the second attempt


def test_persistently_malformed_json_raises_invalid_output(monkeypatch):
    calls = []

    def fake_post(*a, **k):
        calls.append(1)
        return chat_response("not json at all")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(client.LLMInvalidOutput):
        client.generate_json("x", schemas.validate_cards, node="author")

    assert len(calls) == settings.LLM_MAX_RETRIES + 1  # bounded, no infinite loop


def test_missing_required_field_never_reaches_the_caller(monkeypatch):
    """A card without an answer must not be returned for persistence."""
    broken = {"cards": [{"question": "Q?", "difficulty": "easy"}]}
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: chat_response(dumps(broken))
    )

    with pytest.raises(client.LLMInvalidOutput):
        client.generate_json("x", schemas.validate_cards, node="author")


def test_empty_response_is_treated_as_malformed(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: chat_response(""))

    with pytest.raises(client.LLMInvalidOutput):
        client.generate_json("x", schemas.validate_cards, node="author")


def test_missing_choices_is_transient(monkeypatch, no_sleep):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(200, {"choices": []}))

    with pytest.raises(client.LLMUnavailable):
        client.generate_json("x", schemas.validate_cards, node="author")


def test_upstream_error_inside_200_envelope_is_transient(monkeypatch, no_sleep):
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: FakeResponse(200, {"error": {"message": "upstream provider offline"}}),
    )

    with pytest.raises(client.LLMUnavailable):
        client.generate_json("x", schemas.validate_cards, node="author")


# ------------------------------------------------------------------- retries


def test_rate_limit_backs_off_then_succeeds(monkeypatch, no_sleep):
    responses = [
        FakeResponse(429, {}, headers={"Retry-After": "2"}),
        chat_response(dumps(VALID_CARDS)),
    ]
    monkeypatch.setattr(requests, "post", lambda *a, **k: responses.pop(0))

    cards = client.generate_json("x", schemas.validate_cards, node="author")

    assert len(cards) == 1
    assert len(no_sleep) == 1 and no_sleep[0] > 0  # backed off once


def test_backoff_is_exponential_and_bounded(monkeypatch, no_sleep):
    calls = []

    def fake_post(*a, **k):
        calls.append(1)
        return FakeResponse(503, {}, text="service unavailable")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(client.LLMUnavailable):
        client.generate_json("x", schemas.validate_cards, node="author")

    assert len(calls) == settings.LLM_MAX_RETRIES + 1  # bounded
    assert len(no_sleep) == settings.LLM_MAX_RETRIES
    assert no_sleep[1] > no_sleep[0]  # exponential growth (jitter keeps it >0.5x)


def test_timeout_is_retried(monkeypatch, no_sleep):
    calls = []

    def fake_post(*a, **k):
        calls.append(1)
        raise requests.Timeout("read timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(client.LLMUnavailable):
        client.generate_json("x", schemas.validate_cards, node="author")

    assert len(calls) == settings.LLM_MAX_RETRIES + 1


def test_response_format_rejection_retries_without_json_mode(monkeypatch):
    payloads = []

    def fake_post(url, json=None, headers=None, timeout=None):
        payloads.append(json)
        if "response_format" in json:
            return FakeResponse(400, {}, text="model does not support response_format")
        return chat_response(dumps(VALID_CARDS))

    monkeypatch.setattr(requests, "post", fake_post)

    cards = client.generate_json("x", schemas.validate_cards, node="author")

    assert len(cards) == 1
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]


# ------------------------------------------------------------ provider errors


def test_auth_failure_is_not_retried(monkeypatch, no_sleep):
    calls = []

    def fake_post(*a, **k):
        calls.append(1)
        return FakeResponse(401, {}, text="invalid api key")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(client.LLMUnavailable) as exc:
        client.generate_json("x", schemas.validate_cards, node="author")

    assert len(calls) == 1  # a bad key will not fix itself
    assert not no_sleep
    assert DUMMY_KEY not in str(exc.value)


def test_missing_api_key_gives_an_actionable_error(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    with pytest.raises(client.LLMUnavailable) as exc:
        client.generate_json("x", schemas.validate_cards, node="author")

    assert "OPENROUTER_API_KEY" in str(exc.value)


def test_api_key_is_scrubbed_from_error_text(monkeypatch, no_sleep):
    """A provider that echoes the key back must not leak it into an error."""
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: FakeResponse(500, {}, text=f"upstream rejected {DUMMY_KEY}"),
    )

    with pytest.raises(client.LLMUnavailable) as exc:
        client.generate_json("x", schemas.validate_cards, node="author")

    assert DUMMY_KEY not in str(exc.value)
    assert "***" in str(exc.value)


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "banana")

    with pytest.raises(client.LLMUnavailable, match="Unknown LLM_PROVIDER"):
        client.generate_json("x", schemas.validate_cards, node="author")


# ----------------------------------------------------------------- fallback


def test_transient_failure_falls_back_to_ollama(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "llama3:8b")
    monkeypatch.setattr(settings, "OLLAMA_CRITIC_MODEL", "qwen2.5:7b")
    seen = []

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.append(url)
        if "openrouter" in url or "chat/completions" in url:
            return FakeResponse(503, {}, text="overloaded")
        return FakeResponse(200, {"response": dumps(VALID_CARDS)})

    monkeypatch.setattr(requests, "post", fake_post)

    cards = client.generate_json("x", schemas.validate_cards, node="author")

    assert len(cards) == 1
    assert any("chat/completions" in u for u in seen)
    assert any("/api/generate" in u for u in seen)


def test_fallback_uses_the_ollama_model_name(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "llama3:8b")
    monkeypatch.setattr(settings, "OLLAMA_CRITIC_MODEL", "qwen2.5:7b")
    payloads = []

    critique = {"reviews": [{"index": 0, "verdict": "accept", "groundedness": 0.9, "feedback": ""}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        payloads.append((url, json))
        if "chat/completions" in url:
            return FakeResponse(503, {}, text="overloaded")
        return FakeResponse(200, {"response": dumps(critique)})

    monkeypatch.setattr(requests, "post", fake_post)
    reviews = client.generate_json("x", schemas.validate_critique, node="critic")
    assert reviews[0]["verdict"] == "accept"

    ollama_payload = [p for url, p in payloads if "/api/generate" in url][0]
    assert ollama_payload["model"] == "qwen2.5:7b"  # critic knob honoured per provider


def test_no_fallback_when_disabled(monkeypatch, no_sleep):
    seen = []

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.append(url)
        return FakeResponse(503, {}, text="overloaded")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(client.LLMUnavailable):
        client.generate_json("x", schemas.validate_cards, node="author")

    assert all("chat/completions" in url for url in seen)


def test_provider_switch_to_ollama_needs_no_agent_changes(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "LLM_MODEL", "llama3:8b")
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["payload"] = json
        return FakeResponse(200, {"response": dumps(VALID_CARDS)})

    monkeypatch.setattr(requests, "post", fake_post)

    cards = client.generate_json("x", schemas.validate_cards, node="author")

    assert len(cards) == 1
    assert seen["url"].endswith("/api/generate")
    assert seen["payload"]["format"] == "json"
    # The author system prompt travels on the Ollama path too.
    assert "ONLY the retrieved context" in seen["payload"]["system"]


# -------------------------------------------------------- critic -> repair


class StubTools:
    """AgentTools stand-in: fixed evidence, nothing is ever a duplicate."""

    def __init__(self):
        self.saved = []

    def search_corpus(self, query, top_k=None):
        return [
            {"chunk_id": 11, "text": "SM-2 updates the ease factor and interval.", "score": 0.9}
        ]

    def is_duplicate(self, question, against, threshold=None):
        return False, 0.0, None


def test_critic_rejection_routes_through_repair_and_back(monkeypatch):
    """revise -> repair -> re-critique -> accept, with provenance attached."""
    from backend.src.ai.agents import flashcard_agent as fa

    drafts = [
        {"question": "Q1 grounded?", "answer": "A1.", "difficulty": "easy", "evidence": "e"},
        {"question": "Q2 unsupported?", "answer": "A2.", "difficulty": "hard", "evidence": "e"},
    ]
    repaired = [
        {"question": "Q2 fixed?", "answer": "A2 corrected.", "difficulty": "medium", "evidence": "e"}
    ]
    nodes = []

    def fake_generate_json(prompt, validator, *, node="llm", **kwargs):
        nodes.append(node)
        if node == "author":
            return [dict(card) for card in drafts]
        if node == "critic":
            if nodes.count("critic") == 1:
                return [
                    {"index": 0, "verdict": "accept", "groundedness": 0.9, "feedback": ""},
                    {
                        "index": 1,
                        "verdict": "revise",
                        "groundedness": 0.3,
                        "feedback": "answer is not supported by the evidence",
                    },
                ]
            return [{"index": 0, "verdict": "accept", "groundedness": 0.85, "feedback": ""}]
        if node == "repair":
            assert "not supported by the evidence" in prompt  # critic feedback forwarded
            return [dict(card) for card in repaired]
        raise AssertionError(f"unexpected node {node}")

    monkeypatch.setattr(fa, "generate_json", fake_generate_json)

    agent = fa.FlashcardAgent(db=None, instance_id=1)
    agent.tools = StubTools()
    result = fa.AgentResult()

    report = agent._process_topic(
        {"topic": "SM-2", "query": "SM-2", "cards": 2, "difficulty_mix": ["easy", "hard"]},
        known_questions=[],
        result=result,
    )

    assert nodes == ["author", "critic", "repair", "critic"]
    assert report["repair_rounds"] == 1
    assert report["accepted"] == 2
    questions = [card["question"] for card in report["accepted_cards"]]
    assert questions == ["Q1 grounded?", "Q2 fixed?"]
    # Every accepted card carries the chunk ids that grounded it.
    assert all(card["source_chunk_ids"] == [11] for card in report["accepted_cards"])
    assert all("_feedback" not in card for card in report["accepted_cards"])


def test_rejected_cards_are_dropped_not_saved(monkeypatch):
    from backend.src.ai.agents import flashcard_agent as fa

    def fake_generate_json(prompt, validator, *, node="llm", **kwargs):
        if node == "author":
            return [
                {"question": "Made up?", "answer": "Invented.", "difficulty": "easy", "evidence": ""}
            ]
        if node == "critic":
            return [
                {
                    "index": 0,
                    "verdict": "reject",
                    "groundedness": 0.0,
                    "feedback": "not in the evidence at all",
                }
            ]
        raise AssertionError(f"unexpected node {node}")

    monkeypatch.setattr(fa, "generate_json", fake_generate_json)

    agent = fa.FlashcardAgent(db=None, instance_id=1)
    agent.tools = StubTools()
    result = fa.AgentResult()

    report = agent._process_topic(
        {"topic": "SM-2", "query": "SM-2", "cards": 1}, known_questions=[], result=result
    )

    assert report["accepted"] == 0
    assert report["rejected"] == 1
    assert report["accepted_cards"] == []


def test_provider_failure_during_authoring_is_reported_not_raised(monkeypatch):
    """An OpenRouter outage degrades the run instead of 500-ing the request."""
    from backend.src.ai.agents import flashcard_agent as fa

    def fake_generate_json(prompt, validator, *, node="llm", **kwargs):
        raise client.LLMUnavailable("author: provider failed after 3 attempts: rate limited")

    monkeypatch.setattr(fa, "generate_json", fake_generate_json)

    agent = fa.FlashcardAgent(db=None, instance_id=1)
    agent.tools = StubTools()
    result = fa.AgentResult()

    report = agent._process_topic(
        {"topic": "SM-2", "query": "SM-2", "cards": 1}, known_questions=[], result=result
    )

    assert report["accepted"] == 0
    assert any("author failed" in note for note in report["notes"])
    assert result.warnings
