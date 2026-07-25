"""
Unit tests for LLM output validators.

These are what stop a malformed model response from reaching the database, so
they need to normalise the sloppy-but-recoverable cases and reject the rest.
"""

import pytest

from backend.src.ai.llm import schemas


def test_cards_accept_bare_list_and_wrapped_object():
    payload = [{"question": "Q?", "answer": "A.", "difficulty": "easy"}]
    wrapped = {"cards": payload}

    assert schemas.validate_cards(payload)[0]["question"] == "Q?"
    assert schemas.validate_cards(wrapped)[0]["question"] == "Q?"


def test_difficulty_aliases_are_normalised():
    cards = schemas.validate_cards(
        [
            {"question": "Q1", "answer": "A1", "difficulty": "Beginner"},
            {"question": "Q2", "answer": "A2", "difficulty": "ADVANCED"},
            {"question": "Q3", "answer": "A3", "difficulty": "intermediate"},
        ]
    )
    assert [card["difficulty"] for card in cards] == ["easy", "hard", "medium"]


def test_cards_reject_missing_answer():
    with pytest.raises(ValueError, match="answer"):
        schemas.validate_cards([{"question": "Q?", "difficulty": "easy"}])


def test_cards_reject_empty_list():
    with pytest.raises(ValueError):
        schemas.validate_cards([])


def test_critique_normalises_verdict_aliases():
    reviews = schemas.validate_critique(
        [
            {"index": 0, "verdict": "Approved", "groundedness": 90},
            {"index": 1, "verdict": "fix", "groundedness": 0.4},
            {"index": 2, "verdict": "DROP", "groundedness": 0},
        ]
    )
    assert [r["verdict"] for r in reviews] == ["accept", "revise", "reject"]
    # 0-100 scores are rescaled to 0-1.
    assert reviews[0]["groundedness"] == 0.9


def test_critique_rejects_unknown_verdict():
    with pytest.raises(ValueError, match="verdict"):
        schemas.validate_critique([{"index": 0, "verdict": "maybe"}])


def test_coverage_plan_clamps_card_count():
    plan = schemas.validate_coverage_plan(
        [{"topic": "Backprop", "cards": 999}, {"topic": "CNNs", "cards": 0}]
    )
    assert plan[0]["cards"] == 8
    assert plan[1]["cards"] == 1


def test_coverage_plan_defaults_query_to_topic():
    plan = schemas.validate_coverage_plan([{"topic": "Attention"}])
    assert plan[0]["query"] == "Attention"


def test_revision_plan_normalises_actions_and_clamps_priority():
    plan = schemas.validate_revision_plan(
        [{"topic": "CNNs", "action": "re-teach", "priority": 99}]
    )
    assert plan[0]["action"] == "reteach"
    assert plan[0]["priority"] == 5


def test_recommendations_require_title():
    with pytest.raises(ValueError, match="title"):
        schemas.validate_recommendations([{"detail": "do something"}])
