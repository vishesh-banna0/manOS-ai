"""
File: flashcard_agent.py

Purpose:
Retrieval-grounded flashcard authoring agent.

Workflow (a state machine with LLM decision points, not free-form ReAct -
local 7-8B models are unreliable at multi-turn tool selection but dependable
at schema-constrained single-step calls):

    PLAN ---> for each topic: RETRIEVE -> AUTHOR -> CRITIQUE
                                              ^        |
                                              |        v
                                          REPAIR <-- revise
                                                       |
                                                    accept -> SAVE

What makes it agentic rather than a pipeline:
- The planner decides *what deserves a card*, instead of blindly emitting 3
  cards per chunk (which produced hundreds of near-duplicates on a long PDF).
- Control flow branches on model output: accept / revise / reject.
- The loop terminates dynamically - when every card is accepted, or when the
  repair-round budget is exhausted.
- Every card is grounded in retrieved evidence and carries its chunk ids.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ...core.config import settings
from ..llm import schemas
from ..llm.client import LLMInvalidOutput, LLMTrace, LLMUnavailable, generate_json
from .tools import AgentTools


@dataclass
class AgentResult:
    cards_created: int = 0
    topics_planned: int = 0
    drafts: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    repair_rounds: int = 0
    warnings: List[str] = field(default_factory=list)
    topics: List[dict] = field(default_factory=list)
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "cards_created": self.cards_created,
            "topics_planned": self.topics_planned,
            "drafts": self.drafts,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "duplicates": self.duplicates,
            "repair_rounds": self.repair_rounds,
            "warnings": self.warnings,
            "topics": self.topics,
            "trace": self.trace,
        }


def _format_evidence(chunks: List[dict]) -> str:
    """Render retrieved chunks as numbered, citable evidence."""
    blocks = []
    for position, chunk in enumerate(chunks, start=1):
        pages = ""
        if chunk.get("page_start"):
            pages = f" (p.{chunk['page_start']}"
            if chunk.get("page_end") and chunk["page_end"] != chunk["page_start"]:
                pages += f"-{chunk['page_end']}"
            pages += ")"
        blocks.append(f"[{position}]{pages} {chunk.get('text', '')}")
    return "\n\n".join(blocks)


class FlashcardAgent:
    """Authors grounded flashcards for one learning instance."""

    def __init__(self, db: Session, instance_id: int, progress=None):
        """
        Args:
            progress: optional callable(stage=..., message=..., current=...,
                total=..., **counters) used to report progress. A run takes
                minutes, so the caller needs to be able to show what stage it
                is on rather than an opaque spinner.
        """
        self.db = db
        self.instance_id = instance_id
        self.tools = AgentTools(db, instance_id)
        self.trace = LLMTrace()
        self._progress = progress

    def _report(self, **fields) -> None:
        if self._progress:
            self._progress(**fields)

    # ------------------------------------------------------------------ run

    def run(self, max_topics: Optional[int] = None) -> AgentResult:
        result = AgentResult()

        corpus_size = self.tools.corpus_size()
        if corpus_size == 0:
            result.warnings.append(
                "No indexed chunks for this instance. Upload a document first."
            )
            return result

        # --- Node 1: plan coverage ---
        self._report(
            stage="planning",
            message=f"Planning topics from {corpus_size} indexed sections...",
            current=0,
            total=0,
        )

        try:
            plan = self._plan(max_topics or settings.AGENT_MAX_TOPICS)
        except (LLMUnavailable, LLMInvalidOutput) as exc:
            result.warnings.append(f"Planner failed ({exc}); falling back to outline topics.")
            plan = self._fallback_plan(max_topics or settings.AGENT_MAX_TOPICS)

        result.topics_planned = len(plan)
        if not plan:
            result.warnings.append("Planner produced no topics.")
            return result

        # Dedupe against what already exists, and against cards accepted
        # earlier in this same run.
        known_questions = self.tools.existing_questions()

        self._report(
            stage="authoring",
            message=f"Planned {len(plan)} topics.",
            current=0,
            total=len(plan),
        )

        for index, topic_spec in enumerate(plan):
            topic_report = self._process_topic(
                topic_spec, known_questions, result, index, len(plan)
            )
            result.topics.append(topic_report)

            accepted_cards = topic_report.pop("accepted_cards", [])
            for card in accepted_cards:
                known_questions.append(card["question"])

            # Save per topic rather than batching to the end: a run takes
            # minutes, and this way cards are durable as soon as they are
            # written and the client sees the count climb in real time.
            if accepted_cards:
                saved = self.tools.save_flashcards(accepted_cards)
                result.cards_created += len(saved)

            self._report(
                stage="authoring",
                message=f"Finished '{topic_spec['topic'][:45]}'",
                current=index + 1,
                total=len(plan),
                cards_created=result.cards_created,
                duplicates=result.duplicates,
                rejected=result.rejected,
            )

        self._report(
            stage="done",
            message=f"{result.cards_created} flashcards created.",
            current=len(plan),
            total=len(plan),
            cards_created=result.cards_created,
        )

        result.trace = self.trace.summary()
        return result

    # -------------------------------------------------------------- planning

    def _plan(self, max_topics: int) -> List[dict]:
        outline = self.tools.corpus_outline()
        outline_text = "\n".join(
            f"- chunk {item['chunk_id']}: {item['title']}" for item in outline
        )

        prompt = f"""You are planning a flashcard deck for a student.

Below is an outline of a study document - one line per section, showing the
opening words of each section.

OUTLINE:
{outline_text}

Identify the {max_topics} most important distinct topics that deserve
flashcards. Rules:
- Merge sections that cover the same topic into ONE entry.
- Skip front matter, references, and filler.
- Prefer topics a student would be tested on.
- "query" must be a short search phrase that will retrieve that topic's text.

Return ONLY a JSON object with a "topics" array:
{{
  "topics": [
    {{
      "topic": "short topic name",
      "query": "search phrase to retrieve this topic",
      "why": "one sentence on why it matters",
      "cards": 3,
      "difficulty_mix": ["easy", "medium", "hard"]
    }}
  ]
}}"""

        plan = generate_json(
            prompt,
            schemas.validate_coverage_plan,
            node="planner",
            trace=self.trace,
        )
        return plan[:max_topics]

    def _fallback_plan(self, max_topics: int) -> List[dict]:
        """Offline path: derive topics from chunk titles."""
        outline = self.tools.corpus_outline(limit=max_topics * 2)
        seen = set()
        plan = []

        for item in outline:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            key = title.lower()[:40]
            if key in seen:
                continue
            seen.add(key)
            plan.append(
                {
                    "topic": title[:80],
                    "query": title,
                    "why": "",
                    "cards": settings.AGENT_CARDS_PER_TOPIC,
                    "difficulty_mix": ["easy", "medium", "hard"],
                }
            )
            if len(plan) >= max_topics:
                break

        return plan

    # ---------------------------------------------------------- topic worker

    def _process_topic(
        self,
        topic_spec: dict,
        known_questions: List[str],
        result: AgentResult,
        topic_index: int = 0,
        topic_total: int = 0,
    ) -> dict:
        topic = topic_spec["topic"]
        label = f"Topic {topic_index + 1}/{topic_total}: {topic[:45]}"
        report = {
            "topic": topic,
            "retrieved_chunks": 0,
            "drafted": 0,
            "accepted": 0,
            "rejected": 0,
            "duplicates": 0,
            "repair_rounds": 0,
            "accepted_cards": [],
            "notes": [],
        }

        # --- Node 2: retrieve evidence ---
        self._report(
            stage="retrieving",
            message=f"{label} - retrieving sources",
            current=topic_index,
            total=topic_total,
        )
        evidence = self.tools.search_corpus(topic_spec.get("query") or topic)
        report["retrieved_chunks"] = len(evidence)

        if not evidence:
            report["notes"].append("no evidence retrieved; skipped")
            return report

        chunk_ids = [chunk["chunk_id"] for chunk in evidence]
        evidence_text = _format_evidence(evidence)

        # --- Node 3: author drafts ---
        self._report(
            stage="authoring",
            message=f"{label} - writing cards from {len(evidence)} sources",
            current=topic_index,
            total=topic_total,
        )
        try:
            drafts = self._author(topic_spec, evidence_text)
        except (LLMUnavailable, LLMInvalidOutput) as exc:
            report["notes"].append(f"author failed: {exc}")
            result.warnings.append(f"Author failed for topic '{topic}': {exc}")
            return report

        report["drafted"] = len(drafts)
        result.drafts += len(drafts)

        # --- Nodes 4/5: critique and repair loop ---
        pending = drafts
        accepted: List[dict] = []
        rounds = 0

        while pending and rounds <= settings.AGENT_MAX_REPAIR_ROUNDS:
            self._report(
                stage="reviewing",
                message=(
                    f"{label} - reviewing {len(pending)} cards"
                    + (f" (revision {rounds})" if rounds else "")
                ),
                current=topic_index,
                total=topic_total,
            )
            try:
                reviews = self._critique(topic, pending, evidence_text)
            except (LLMUnavailable, LLMInvalidOutput) as exc:
                # Critic unavailable: accept drafts rather than lose the work,
                # but mark them so the eval harness can tell them apart.
                report["notes"].append(f"critic unavailable ({exc}); accepting unreviewed")
                for card in pending:
                    card["groundedness"] = None
                accepted.extend(pending)
                pending = []
                break

            review_by_index = {review["index"]: review for review in reviews}
            next_round: List[dict] = []

            for index, card in enumerate(pending):
                review = review_by_index.get(index)
                if review is None:
                    # Critic skipped this card; treat as accept-with-unknown.
                    card["groundedness"] = None
                    accepted.append(card)
                    continue

                card["groundedness"] = review["groundedness"]

                if review["verdict"] == "accept":
                    accepted.append(card)
                elif review["verdict"] == "reject":
                    report["rejected"] += 1
                    result.rejected += 1
                elif rounds < settings.AGENT_MAX_REPAIR_ROUNDS:
                    card["_feedback"] = review["feedback"]
                    next_round.append(card)
                else:
                    # Out of repair budget - drop rather than save a card the
                    # critic still considers wrong.
                    report["rejected"] += 1
                    result.rejected += 1

            if not next_round:
                break

            rounds += 1
            report["repair_rounds"] = rounds
            result.repair_rounds += 1

            self._report(
                stage="repairing",
                message=f"{label} - revising {len(next_round)} cards the reviewer rejected",
                current=topic_index,
                total=topic_total,
            )
            try:
                pending = self._repair(topic, next_round, evidence_text)
            except (LLMUnavailable, LLMInvalidOutput) as exc:
                report["notes"].append(f"repair failed: {exc}")
                break

        # --- Semantic dedupe before persisting ---
        for card in accepted:
            is_dup, score, match = self.tools.is_duplicate(card["question"], known_questions)
            if is_dup:
                report["duplicates"] += 1
                result.duplicates += 1
                report["notes"].append(
                    f"dropped duplicate (sim={score:.2f}): {card['question'][:60]}"
                )
                continue

            card["topic"] = topic
            card["source_chunk_ids"] = chunk_ids
            card.pop("_feedback", None)
            report["accepted_cards"].append(card)
            known_questions.append(card["question"])

        report["accepted"] = len(report["accepted_cards"])
        result.accepted += report["accepted"]
        return report

    # ----------------------------------------------------------- LLM  nodes

    def _author(self, topic_spec: dict, evidence_text: str) -> List[dict]:
        count = topic_spec.get("cards", settings.AGENT_CARDS_PER_TOPIC)
        mix = topic_spec.get("difficulty_mix") or ["easy", "medium", "hard"]

        prompt = f"""You are an expert teacher writing flashcards.

TOPIC: {topic_spec['topic']}

EVIDENCE (the ONLY source you may use):
{evidence_text}

Write {count} flashcards about this topic.

Hard rules:
- Every answer must be fully supported by the EVIDENCE above. Do not add
  outside knowledge. If the evidence does not support a card, write fewer.
- Questions must stand alone - never say "the text", "the passage", "above",
  or "according to the document".
- Answers must be self-contained and 1-3 sentences.
- "evidence" must quote the exact sentence(s) from the EVIDENCE that support
  the answer.
- Aim for this difficulty mix: {', '.join(mix)}.

Return ONLY a JSON object with a "cards" array of exactly {count} entries:
{{
  "cards": [
    {{
      "question": "...",
      "answer": "...",
      "difficulty": "easy|medium|hard",
      "evidence": "exact supporting quote"
    }}
  ]
}}"""

        return generate_json(
            prompt,
            schemas.validate_cards,
            node="author",
            trace=self.trace,
        )

    def _critique(self, topic: str, cards: List[dict], evidence_text: str) -> List[dict]:
        cards_json = json.dumps(
            [
                {"index": index, "question": card["question"], "answer": card["answer"],
                 "difficulty": card["difficulty"]}
                for index, card in enumerate(cards)
            ],
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""You are a strict reviewer checking flashcards against source evidence.

TOPIC: {topic}

EVIDENCE:
{evidence_text}

CARDS TO REVIEW:
{cards_json}

For each card, judge:
1. GROUNDED - is the answer fully supported by the EVIDENCE? An answer that is
   true in general but not stated in the evidence is NOT grounded.
2. SELF-CONTAINED - can the question be understood without seeing the evidence?
   Cards referring to "the text" or "the passage" fail.
3. DIFFICULTY - is the label honest? An "hard" card that only asks for a
   definition is mislabelled.

Verdicts:
- "accept": all three checks pass
- "revise": fixable problem - explain precisely what to fix in "feedback"
- "reject": not supported by the evidence at all

Be critical. Do not accept a card merely because it sounds plausible.

Return ONLY a JSON object with a "reviews" array containing EXACTLY
{len(cards)} entries - one per card, in index order:
{{
  "reviews": [
    {{
      "index": 0,
      "verdict": "accept|revise|reject",
      "groundedness": 0.0,
      "feedback": "what is wrong and how to fix it"
    }}
  ]
}}"""

        return generate_json(
            prompt,
            schemas.validate_critique,
            node="critic",
            model=settings.CRITIC_MODEL,
            trace=self.trace,
        )

    def _repair(self, topic: str, cards: List[dict], evidence_text: str) -> List[dict]:
        cards_json = json.dumps(
            [
                {
                    "question": card["question"],
                    "answer": card["answer"],
                    "difficulty": card["difficulty"],
                    "reviewer_feedback": card.get("_feedback", ""),
                }
                for card in cards
            ],
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""You are revising flashcards a reviewer rejected.

TOPIC: {topic}

EVIDENCE (the ONLY source you may use):
{evidence_text}

CARDS AND REVIEWER FEEDBACK:
{cards_json}

Rewrite each card to address its reviewer_feedback exactly. Keep what was
already correct. Every answer must be supported by the EVIDENCE, and every
question must stand alone.

Return ONLY a JSON object with a "cards" array, in the same order, containing
exactly {len(cards)} entries:
{{
  "cards": [
    {{
      "question": "...",
      "answer": "...",
      "difficulty": "easy|medium|hard",
      "evidence": "exact supporting quote"
    }}
  ]
}}"""

        return generate_json(
            prompt,
            schemas.validate_cards,
            node="repair",
            trace=self.trace,
        )


def run_flashcard_agent(
    db: Session,
    instance_id: int,
    max_topics: Optional[int] = None,
    progress=None,
) -> dict:
    """Convenience entry point used by the service/API layer."""
    agent = FlashcardAgent(db, instance_id, progress=progress)
    return agent.run(max_topics=max_topics).to_dict()
