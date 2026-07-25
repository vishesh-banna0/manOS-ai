"""
File: revision_agent.py

Purpose:
Revision planning agent.

SM-2 answers "when should this card come back?" one card at a time. It cannot
answer "this person keeps failing backpropagation - should they keep drilling
the same three cards, or be re-taught from the source?". That is what this
agent decides, at topic level, from the review log.

Workflow:
    OBSERVE (topic accuracy + lapse stats from ReviewLog)
      -> DECIDE (LLM picks an action per weak topic)
      -> ACT (apply the action through tools)

Actions:
- reschedule : bring the topic forward in the queue
- drill      : compress intervals; the student is close but inconsistent
- reteach    : retrieve source material and author remedial easier cards
- promote    : the topic is solid; push it further out
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ...core.config import settings
from ..llm import schemas
from ..llm.client import LLMInvalidOutput, LLMTrace, LLMUnavailable, generate_json
from .flashcard_agent import FlashcardAgent, _format_evidence
from .tools import AgentTools

# Days until next review for each action.
ACTION_SCHEDULE = {
    "drill": 0,
    "reschedule": 1,
    "reteach": 0,
    "promote": 7,
}

WEAK_ACCURACY = 0.6
STRONG_ACCURACY = 0.85
MIN_REVIEWS_FOR_SIGNAL = 3


@dataclass
class RevisionResult:
    plan: List[dict] = field(default_factory=list)
    actions_applied: int = 0
    cards_rescheduled: int = 0
    remedial_cards_created: int = 0
    topics_analysed: int = 0
    warnings: List[str] = field(default_factory=list)
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plan": self.plan,
            "actions_applied": self.actions_applied,
            "cards_rescheduled": self.cards_rescheduled,
            "remedial_cards_created": self.remedial_cards_created,
            "topics_analysed": self.topics_analysed,
            "warnings": self.warnings,
            "trace": self.trace,
        }


class RevisionAgent:
    def __init__(self, db: Session, instance_id: int):
        self.db = db
        self.instance_id = instance_id
        self.tools = AgentTools(db, instance_id)
        self.trace = LLMTrace()

    def run(self, apply_actions: bool = True) -> RevisionResult:
        result = RevisionResult()

        # --- OBSERVE ---
        performance = self.tools.topic_performance()
        result.topics_analysed = len(performance)

        if not performance:
            result.warnings.append(
                "No review history yet. Review some flashcards first - the plan "
                "is derived from actual performance, not guesses."
            )
            return result

        # --- DECIDE ---
        try:
            plan = self._decide(performance)
        except (LLMUnavailable, LLMInvalidOutput) as exc:
            result.warnings.append(f"Planner unavailable ({exc}); using rule-based plan.")
            plan = self._rule_based_plan(performance)

        # --- ACT ---
        for entry in plan:
            topic = entry["topic"]
            action = entry["action"]
            stats = next((p for p in performance if p["topic"] == topic), None)
            entry["accuracy"] = stats["accuracy"] if stats else None
            entry["reviews"] = stats["reviews"] if stats else 0

            if not apply_actions:
                continue

            days = ACTION_SCHEDULE.get(action, 1)
            moved = self.tools.reschedule_topic(topic, days)
            entry["cards_rescheduled"] = moved
            result.cards_rescheduled += moved
            result.actions_applied += 1

            if action == "reteach":
                created = self._reteach(topic, result)
                entry["remedial_cards_created"] = created
                result.remedial_cards_created += created

        result.plan = plan
        result.trace = self.trace.summary()
        return result

    # ------------------------------------------------------------- decision

    def _decide(self, performance: List[dict]) -> List[dict]:
        stats_json = json.dumps(
            [
                {
                    "topic": item["topic"],
                    "accuracy": item["accuracy"],
                    "reviews": item["reviews"],
                }
                for item in performance[:20]
            ],
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""You are planning a student's next revision session.

Here is their measured performance per topic (accuracy is 0-1, reviews is how
many times they have been tested on it):

{stats_json}

For each topic, choose ONE action:
- "reteach"   : accuracy is low AND they have had several attempts - drilling
                the same cards is not working, they need the material again
- "drill"     : accuracy is mediocre but improving, or too few reviews to
                judge - keep practising soon
- "reschedule": accuracy is acceptable - normal spacing
- "promote"   : accuracy is high and well-evidenced - push it further out

Guidance:
- Do not choose "reteach" on fewer than {MIN_REVIEWS_FOR_SIGNAL} reviews; there
  is not enough signal. Choose "drill" instead.
- priority: 1 = most urgent, 5 = least.

Return ONLY a JSON object with a "plan" array, one entry per topic:
{{
  "plan": [
    {{
      "topic": "...",
      "action": "reteach|drill|reschedule|promote",
      "priority": 1,
      "rationale": "one sentence grounded in the numbers"
    }}
  ]
}}"""

        plan = generate_json(
            prompt,
            schemas.validate_revision_plan,
            node="revision_planner",
            trace=self.trace,
        )

        # Guard the model against itself: reteaching on thin evidence wastes
        # generation budget and frustrates the student.
        by_topic = {item["topic"]: item for item in performance}
        for entry in plan:
            stats = by_topic.get(entry["topic"])
            if not stats:
                continue
            if entry["action"] == "reteach" and stats["reviews"] < MIN_REVIEWS_FOR_SIGNAL:
                entry["action"] = "drill"
                entry["rationale"] = (
                    f"{entry['rationale']} (downgraded to drill: only "
                    f"{stats['reviews']} reviews)"
                ).strip()

        plan.sort(key=lambda entry: entry["priority"])
        return plan

    def _rule_based_plan(self, performance: List[dict]) -> List[dict]:
        """Deterministic fallback when the LLM is unavailable."""
        plan = []
        for item in performance:
            accuracy = item["accuracy"]
            reviews = item["reviews"]

            if accuracy < WEAK_ACCURACY and reviews >= MIN_REVIEWS_FOR_SIGNAL:
                action, priority = "reteach", 1
            elif accuracy < WEAK_ACCURACY:
                action, priority = "drill", 2
            elif accuracy >= STRONG_ACCURACY and reviews >= MIN_REVIEWS_FOR_SIGNAL:
                action, priority = "promote", 5
            else:
                action, priority = "reschedule", 3

            plan.append(
                {
                    "topic": item["topic"],
                    "action": action,
                    "priority": priority,
                    "rationale": (
                        f"accuracy {accuracy:.0%} over {reviews} reviews (rule-based)"
                    ),
                }
            )

        plan.sort(key=lambda entry: entry["priority"])
        return plan

    # -------------------------------------------------------------- reteach

    def _reteach(self, topic: str, result: RevisionResult) -> int:
        """
        Author easier, differently-angled cards for a failing topic.

        Reuses the flashcard agent's author + critic nodes so remedial cards
        get the same grounding guarantees as the originals.
        """
        evidence = self.tools.search_corpus(topic, k=settings.RETRIEVAL_TOP_K)
        if not evidence:
            result.warnings.append(f"No source material found to reteach '{topic}'.")
            return 0

        agent = FlashcardAgent(self.db, self.instance_id)
        agent.trace = self.trace

        topic_spec = {
            "topic": topic,
            "query": topic,
            "cards": 2,
            # Remedial cards deliberately sit below the difficulty that failed.
            "difficulty_mix": ["easy", "easy", "medium"],
        }
        evidence_text = _format_evidence(evidence)

        try:
            drafts = agent._author(topic_spec, evidence_text)
        except (LLMUnavailable, LLMInvalidOutput) as exc:
            result.warnings.append(f"Could not author remedial cards for '{topic}': {exc}")
            return 0

        try:
            reviews = agent._critique(topic, drafts, evidence_text)
            accepted = [
                card
                for index, card in enumerate(drafts)
                if next(
                    (r["verdict"] for r in reviews if r["index"] == index), "accept"
                ) == "accept"
            ]
        except (LLMUnavailable, LLMInvalidOutput):
            accepted = drafts

        known = self.tools.existing_questions()
        fresh = []
        for card in accepted:
            is_dup, _, _ = self.tools.is_duplicate(card["question"], known)
            if is_dup:
                continue
            card["topic"] = topic
            card["source_chunk_ids"] = [chunk["chunk_id"] for chunk in evidence]
            card["origin"] = "revision_agent"
            fresh.append(card)
            known.append(card["question"])

        saved = self.tools.save_flashcards(fresh)
        return len(saved)


def run_revision_agent(db: Session, instance_id: int, apply_actions: bool = True) -> dict:
    return RevisionAgent(db, instance_id).run(apply_actions=apply_actions).to_dict()
