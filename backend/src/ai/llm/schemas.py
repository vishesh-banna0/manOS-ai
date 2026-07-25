"""
File: schemas.py

Purpose:
Validators for LLM JSON output.

Each validator normalises as much as it reasonably can (case, aliases, missing
optional keys) and raises ValueError on anything structurally wrong. The error
text is fed back to the model on retry, so messages are written to be
actionable by the model, not just by a human reader.
"""

from __future__ import annotations

from typing import Any, Dict, List

DIFFICULTIES = ("easy", "medium", "hard")
VERDICTS = ("accept", "revise", "reject")
ACTIONS = ("reschedule", "reteach", "promote", "drill")


def _as_list(payload: Any, key: str) -> List[Any]:
    """Accept either a bare list or {key: [...]} - models produce both."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if key in payload and isinstance(payload[key], list):
            return payload[key]
        # Single-key dict wrapping a list under an unexpected name.
        values = [v for v in payload.values() if isinstance(v, list)]
        if len(values) == 1:
            return values[0]
    raise ValueError(f"expected a JSON list (or an object with a '{key}' list)")


def _text(value: Any, field: str, max_len: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field}' must be a non-empty string")
    return value.strip()[:max_len]


def _difficulty(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in DIFFICULTIES:
        return text
    # Common near-misses from small models.
    alias = {
        "beginner": "easy",
        "basic": "easy",
        "simple": "easy",
        "intermediate": "medium",
        "moderate": "medium",
        "advanced": "hard",
        "difficult": "hard",
        "expert": "hard",
    }
    if text in alias:
        return alias[text]
    raise ValueError(f"'difficulty' must be one of {DIFFICULTIES}, got {value!r}")


def _score(value: Any, field: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{field}' must be a number between 0 and 1")
    if score > 1.0:  # models often answer 0-100
        score = score / 100.0
    return max(0.0, min(1.0, score))


# --------------------------------------------------------------------- planner


def validate_coverage_plan(payload: Any) -> List[Dict]:
    """
    Expected: [{"topic": str, "why": str, "cards": int, "difficulty_mix": [...]}]
    """
    items = _as_list(payload, "topics")
    if not items:
        raise ValueError("coverage plan must contain at least one topic")

    plan = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"topic at position {index} must be an object")

        topic = _text(item.get("topic") or item.get("name"), "topic", 255)

        try:
            cards = int(item.get("cards", item.get("card_count", 3)))
        except (TypeError, ValueError):
            cards = 3
        cards = max(1, min(8, cards))

        mix_raw = item.get("difficulty_mix") or item.get("difficulties") or []
        mix = []
        if isinstance(mix_raw, list):
            for entry in mix_raw:
                try:
                    mix.append(_difficulty(entry))
                except ValueError:
                    continue

        plan.append(
            {
                "topic": topic,
                "why": str(item.get("why") or item.get("reason") or "").strip()[:500],
                "cards": cards,
                "difficulty_mix": mix,
                "query": str(item.get("query") or topic).strip()[:500],
            }
        )

    return plan


# ---------------------------------------------------------------------- author


def validate_cards(payload: Any) -> List[Dict]:
    """
    Expected: [{"question": str, "answer": str, "difficulty": str,
                "evidence": str}]
    """
    items = _as_list(payload, "cards")
    if not items:
        raise ValueError("must return at least one card")

    cards = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"card at position {index} must be an object")

        cards.append(
            {
                "question": _text(item.get("question"), "question", 1000),
                "answer": _text(item.get("answer"), "answer", 2000),
                "difficulty": _difficulty(item.get("difficulty", "medium")),
                "evidence": str(item.get("evidence") or "").strip()[:1000],
            }
        )

    return cards


# ---------------------------------------------------------------------- critic


def validate_critique(payload: Any) -> List[Dict]:
    """
    Expected: [{"index": int, "verdict": str, "groundedness": float,
                "feedback": str}]
    """
    items = _as_list(payload, "reviews")
    if not items:
        raise ValueError("must return one review per card")

    reviews = []
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"review at position {position} must be an object")

        verdict = str(item.get("verdict") or "").strip().lower()
        if verdict not in VERDICTS:
            alias = {
                "accepted": "accept",
                "approve": "accept",
                "approved": "accept",
                "ok": "accept",
                "pass": "accept",
                "good": "accept",
                "fix": "revise",
                "revised": "revise",
                "edit": "revise",
                "rejected": "reject",
                "fail": "reject",
                "drop": "reject",
            }
            if verdict not in alias:
                raise ValueError(f"'verdict' must be one of {VERDICTS}, got {verdict!r}")
            verdict = alias[verdict]

        try:
            index = int(item.get("index", position))
        except (TypeError, ValueError):
            index = position

        reviews.append(
            {
                "index": index,
                "verdict": verdict,
                "groundedness": _score(item.get("groundedness", 0.5), "groundedness"),
                "feedback": str(item.get("feedback") or "").strip()[:600],
            }
        )

    return reviews


# ------------------------------------------------------------- revision agent


def validate_revision_plan(payload: Any) -> List[Dict]:
    """
    Expected: [{"topic": str, "action": str, "priority": int, "rationale": str}]
    """
    items = _as_list(payload, "plan")
    if not items:
        raise ValueError("revision plan must contain at least one entry")

    plan = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"plan entry at position {index} must be an object")

        action = str(item.get("action") or "").strip().lower()
        if action not in ACTIONS:
            alias = {
                "review": "reschedule",
                "repeat": "drill",
                "practice": "drill",
                "relearn": "reteach",
                "re-teach": "reteach",
                "teach": "reteach",
                "advance": "promote",
                "skip": "promote",
            }
            if action not in alias:
                raise ValueError(f"'action' must be one of {ACTIONS}, got {action!r}")
            action = alias[action]

        try:
            priority = int(item.get("priority", 3))
        except (TypeError, ValueError):
            priority = 3

        plan.append(
            {
                "topic": _text(item.get("topic"), "topic", 255),
                "action": action,
                "priority": max(1, min(5, priority)),
                "rationale": str(item.get("rationale") or item.get("why") or "").strip()[:500],
            }
        )

    return plan


# ------------------------------------------------------- recommendation agent


def validate_recommendations(payload: Any) -> List[Dict]:
    """
    Expected: [{"title": str, "detail": str, "category": str, "priority": int}]
    """
    items = _as_list(payload, "recommendations")
    if not items:
        raise ValueError("must return at least one recommendation")

    recommendations = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"recommendation at position {index} must be an object")

        try:
            priority = int(item.get("priority", 3))
        except (TypeError, ValueError):
            priority = 3

        recommendations.append(
            {
                "title": _text(item.get("title"), "title", 200),
                "detail": str(item.get("detail") or item.get("description") or "").strip()[:800],
                "category": str(item.get("category") or "study").strip().lower()[:40],
                "priority": max(1, min(5, priority)),
            }
        )

    return recommendations
