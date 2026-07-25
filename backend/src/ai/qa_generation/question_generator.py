"""
File: question_generator.py

Purpose:
Single-shot Q&A generation from one chunk of text.

This is the UNGROUNDED baseline. Production flashcard authoring goes through
FlashcardAgent (plan -> retrieve -> author -> critique -> repair), which is
what actually ships. This module is kept for two reasons:

1. The evaluation harness compares it against the agent, so "the agent
   improves generation quality" is a measured claim rather than an assertion.
2. It is a cheap offline path when the corpus has not been indexed.

Do not wire this into the API - use FlashcardAgent.
"""

from __future__ import annotations

import re
from typing import Dict, List

from ...core.config import settings
from ..llm import schemas
from ..llm.client import LLMInvalidOutput, LLMUnavailable, generate_json


def _normalize_topic(text: str) -> str:
    words = [word for word in re.findall(r"[A-Za-z0-9]+", text) if word]
    if not words:
        return "this topic"
    return " ".join(words[:6])


def _fallback_questions(chunk_text: str) -> List[Dict]:
    """
    Extractive fallback when no model is reachable.

    Produces genuinely low-quality cards - templated questions, raw sentences
    as answers. It exists so the pipeline degrades instead of crashing, and
    the eval harness scores it as the quality floor.
    """
    topic = _normalize_topic(chunk_text)
    raw_sentences = re.split(r"(?<=[.!?])\s+", chunk_text)

    sentences = []
    seen = set()
    for sentence in raw_sentences:
        cleaned = " ".join(sentence.split()).strip()
        if len(cleaned) < 40:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        sentences.append(cleaned)

    if not sentences:
        snippet = " ".join(chunk_text.split())[:240].strip()
        if not snippet:
            return []
        sentences = [snippet]

    prompts = [
        ("easy", f"What is one key idea from {topic}?"),
        ("medium", f"How would you summarize this point about {topic}?"),
        ("hard", f"Why is this statement important in the context of {topic}?"),
    ]

    fallback = []
    for index, (difficulty, question) in enumerate(prompts):
        answer = sentences[min(index, len(sentences) - 1)]
        fallback.append(
            {
                "question": question,
                "answer": answer,
                "difficulty": difficulty,
                "topic": topic,
                "evidence": answer,
            }
        )

    return fallback


def generate_questions(chunk_text: str, count: int = 3) -> List[Dict]:
    """
    Generate Q&A pairs from a single chunk.

    Returns:
        List of dicts with question / answer / difficulty / topic / evidence.
        Never raises - falls back to extractive generation.
    """
    if not chunk_text or not chunk_text.strip():
        return []

    prompt = f"""You are an expert teacher.

From the following content, generate {count} high-quality questions.

Rules:
- Include a mix of easy, medium and hard questions
- Answers must be correct and self-contained
- Questions must not refer to "the text" or "the passage"

CONTENT:
\"\"\"
{chunk_text}
\"\"\"

Return ONLY a JSON object with a "cards" array of {count} entries:
{{
  "cards": [
    {{
      "question": "...",
      "answer": "...",
      "difficulty": "easy|medium|hard",
      "evidence": "supporting quote from the content"
    }}
  ]
}}"""

    try:
        cards = generate_json(
            prompt,
            schemas.validate_cards,
            node="baseline_generator",
            model=settings.LLM_MODEL,
        )
    except (LLMUnavailable, LLMInvalidOutput) as exc:
        print(f"[question_generator] falling back to extractive generation: {exc}")
        return _fallback_questions(chunk_text)

    topic = _normalize_topic(chunk_text)
    for card in cards:
        card.setdefault("topic", topic)

    return cards
