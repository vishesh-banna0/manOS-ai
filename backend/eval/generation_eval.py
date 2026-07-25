"""
File: generation_eval.py

Purpose:
Measure flashcard generation quality.

Scored dimensions:
- groundedness   : is the answer supported by the source? measured two ways -
                   an LLM judge, and deterministic lexical overlap. Reported
                   separately because they fail differently: a correct
                   paraphrase scores low lexically but high with the judge,
                   while a hallucination scores low on both.
- self-contained : does the question stand alone? (deterministic heuristic)
- duplicate rate : how much of the deck is near-redundant
- difficulty balance : is the easy/medium/hard mix actually spread

Also runs an A/B: the agent (retrieval-grounded, critiqued) against the
ungrounded single-chunk baseline in question_generator.py, on the same
chunks - so "the agent improves quality" is a number, not a claim.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..src.ai.llm import schemas
from ..src.ai.llm.client import LLMInvalidOutput, LLMUnavailable, generate_json
from ..src.ai.qa_generation.question_generator import generate_questions
from ..src.core.config import settings
from ..src.models.chunk import Chunk
from ..src.models.flashcard import Flashcard
from .metrics import (
    difficulty_distribution,
    distribution_balance,
    duplicate_rate,
    is_self_contained,
    lexical_groundedness,
)


def judge_groundedness(question: str, answer: str, evidence: str) -> Optional[float]:
    """
    LLM-as-judge faithfulness score in [0, 1].

    Returns None when the judge is unavailable, so callers can distinguish
    "unmeasured" from "measured as bad".
    """
    def validate(payload):
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
        if "score" not in payload:
            raise ValueError("missing 'score'")
        try:
            score = float(payload["score"])
        except (TypeError, ValueError):
            raise ValueError("'score' must be a number between 0 and 1")
        if score > 1:
            score /= 100.0
        return max(0.0, min(1.0, score))

    # Generous cap: agent cards cite several retrieved chunks, and truncating
    # too early would drop the supporting passage and score a grounded card as
    # a hallucination.
    prompt = f"""You are grading whether a flashcard answer is supported by its source.

SOURCE:
\"\"\"
{evidence[:12000]}
\"\"\"

QUESTION: {question}
ANSWER: {answer}

Score how fully the SOURCE supports the ANSWER:
- 1.0  every claim in the answer is stated in the source
- 0.5  partially supported; some claims are not in the source
- 0.0  not supported, or contradicts the source

An answer that is true in general but absent from the SOURCE scores low.

Return ONLY JSON: {{"score": 0.0, "reason": "one sentence"}}"""

    try:
        return generate_json(
            prompt,
            validate,
            node="groundedness_judge",
            model=settings.CRITIC_MODEL,
            temperature=0.0,
        )
    except (LLMUnavailable, LLMInvalidOutput):
        return None


def evaluate_cards(
    cards: List[Dict],
    use_judge: bool = True,
    judge_sample: int = 20,
) -> Dict:
    """
    Score a list of {question, answer, difficulty, evidence} dicts.

    The judge is sampled rather than run on every card - it is the slowest
    part of the harness and the estimate stabilises quickly.
    """
    if not cards:
        return {"cards": 0}

    questions = [card["question"] for card in cards]
    difficulties = [card.get("difficulty", "medium") for card in cards]

    lexical_scores = [
        lexical_groundedness(card["answer"], card.get("evidence") or "")
        for card in cards
    ]
    self_contained = [is_self_contained(card["question"]) for card in cards]

    report = {
        "cards": len(cards),
        "lexical_groundedness_mean": round(sum(lexical_scores) / len(lexical_scores), 4),
        "lexical_groundedness_below_0.3": sum(1 for s in lexical_scores if s < 0.3),
        "self_contained_rate": round(sum(self_contained) / len(self_contained), 4),
        "duplicate_rate": duplicate_rate(questions),
        "difficulty_distribution": difficulty_distribution(difficulties),
        "difficulty_balance": distribution_balance(difficulties),
        "avg_answer_words": round(
            sum(len(card["answer"].split()) for card in cards) / len(cards), 1
        ),
        "judge_groundedness_mean": None,
        "judge_sampled": 0,
    }

    if use_judge:
        sample = cards[:judge_sample]
        scores = []
        for card in sample:
            evidence = card.get("evidence") or ""
            if not evidence:
                continue
            score = judge_groundedness(card["question"], card["answer"], evidence)
            if score is not None:
                scores.append(score)

        if scores:
            report["judge_groundedness_mean"] = round(sum(scores) / len(scores), 4)
            report["judge_groundedness_below_0.5"] = sum(1 for s in scores if s < 0.5)
            report["judge_sampled"] = len(scores)

    return report


def evaluate_stored_deck(db: Session, instance_id: int, use_judge: bool = True) -> Dict:
    """
    Score the deck currently in the database.

    Evidence is reconstructed from each card's source_chunk_ids, which is
    exactly the provenance the authoring agent recorded.
    """
    cards = (
        db.query(Flashcard).filter(Flashcard.instance_id == instance_id).all()
    )
    if not cards:
        return {"cards": 0, "note": "No flashcards stored for this instance."}

    chunk_texts = {
        chunk.id: chunk.text
        for chunk in db.query(Chunk).filter(Chunk.instance_id == instance_id).all()
    }

    payload = []
    ungrounded = 0
    for card in cards:
        chunk_ids = card.source_chunk_ids or []
        evidence = " ".join(chunk_texts.get(cid, "") for cid in chunk_ids).strip()
        if not evidence:
            ungrounded += 1
        payload.append(
            {
                "question": card.question,
                "answer": card.answer,
                "difficulty": card.difficulty or "medium",
                "evidence": evidence,
            }
        )

    report = evaluate_cards(payload, use_judge=use_judge)
    report["cards_without_provenance"] = ungrounded
    report["provenance_rate"] = round(1 - ungrounded / len(cards), 4)

    stored_groundedness = [
        card.groundedness for card in cards if card.groundedness is not None
    ]
    if stored_groundedness:
        critic_mean = round(sum(stored_groundedness) / len(stored_groundedness), 4)
        report["critic_groundedness_mean"] = critic_mean
        report["critic_scored_cards"] = len(stored_groundedness)

        # The single most useful number this harness produces. The critic runs
        # inside the authoring loop and decides what gets saved; the judge is
        # an independent pass with a different prompt. When the critic scores
        # much higher than the judge, the loop is rubber-stamping its own work
        # and the accept/revise gate is not doing its job.
        judge_mean = report.get("judge_groundedness_mean")
        if isinstance(judge_mean, (int, float)):
            gap = round(critic_mean - judge_mean, 4)
            report["critic_vs_judge_gap"] = gap
            if gap > 0.25:
                report["critic_calibration_warning"] = (
                    f"The in-loop critic scored groundedness {critic_mean} but an "
                    f"independent judge scored {judge_mean} (gap {gap:+.2f}). The "
                    f"critic is likely over-accepting. Point CRITIC_MODEL at a "
                    f"stronger model than the author, and re-measure."
                )

    if len(cards) < 20:
        report["sample_warning"] = (
            f"Only {len(cards)} cards scored - too few to compare configurations "
            f"reliably. Treat these numbers as directional."
        )

    return report


def compare_agent_vs_baseline(
    db: Session,
    instance_id: int,
    sample_chunks: int = 5,
    use_judge: bool = True,
    seed: int = 42,
) -> Dict:
    """
    A/B the ungrounded baseline generator against the stored agent deck.

    The baseline runs live on sampled chunks; the agent side is the deck it
    already produced. Both are scored with identical metrics.
    """
    chunks = db.query(Chunk).filter(Chunk.instance_id == instance_id).all()
    if not chunks:
        return {"error": "No chunks indexed for this instance."}

    random.Random(seed).shuffle(chunks)
    selected = chunks[:sample_chunks]

    baseline_cards = []
    for chunk in selected:
        for card in generate_questions(chunk.text):
            baseline_cards.append(
                {
                    "question": card["question"],
                    "answer": card["answer"],
                    "difficulty": card.get("difficulty", "medium"),
                    # The baseline sees only this chunk, so that is its evidence.
                    "evidence": chunk.text,
                }
            )

    baseline_report = evaluate_cards(baseline_cards, use_judge=use_judge)
    agent_report = evaluate_stored_deck(db, instance_id, use_judge=use_judge)

    deltas = {}
    for key in (
        "lexical_groundedness_mean",
        "judge_groundedness_mean",
        "self_contained_rate",
        "duplicate_rate",
        "difficulty_balance",
    ):
        agent_value = agent_report.get(key)
        baseline_value = baseline_report.get(key)
        if isinstance(agent_value, (int, float)) and isinstance(baseline_value, (int, float)):
            deltas[key] = round(agent_value - baseline_value, 4)

    return {
        "chunks_sampled": len(selected),
        "baseline_cards": len(baseline_cards),
        "agent_cards": agent_report.get("cards", 0),
        "baseline_ungrounded": baseline_report,
        "agent_grounded": agent_report,
        "delta_agent_minus_baseline": deltas,
        "note": (
            "duplicate_rate: lower is better. All other deltas: higher is better."
        ),
        "methodology_caveat": (
            "The two sides do not see identical evidence: baseline cards are "
            "judged against the single chunk they were generated from, agent "
            "cards against all the chunks they cite. That favours neither "
            "consistently, but it means small deltas are noise. Compare on a "
            "deck of 50+ cards before drawing conclusions."
        ),
    }
