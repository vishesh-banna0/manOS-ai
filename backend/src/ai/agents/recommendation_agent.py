"""
File: recommendation_agent.py

Purpose:
Personalised learning recommendations.

Distinct from the revision agent: that one *acts* on the schedule, this one
*advises* the learner. It gathers evidence from several sources (topic
accuracy, due backlog, test history, coverage gaps between the corpus and the
deck), then asks the model for concrete, prioritised next steps.

Every recommendation is anchored to a number from the evidence pack, so the
output cannot drift into generic study advice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.chunk import Chunk
from ...models.flashcard import Flashcard
from ...models.test import Test
from ..llm import schemas
from ..llm.client import LLMInvalidOutput, LLMTrace, LLMUnavailable, generate_json
from .tools import AgentTools


@dataclass
class RecommendationResult:
    recommendations: List[dict] = field(default_factory=list)
    evidence: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    trace: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "recommendations": self.recommendations,
            "evidence": self.evidence,
            "warnings": self.warnings,
            "trace": self.trace,
        }


class RecommendationAgent:
    def __init__(self, db: Session, instance_id: int):
        self.db = db
        self.instance_id = instance_id
        self.tools = AgentTools(db, instance_id)
        self.trace = LLMTrace()

    def run(self, limit: int = 5) -> RecommendationResult:
        result = RecommendationResult()
        evidence = self._gather_evidence()
        result.evidence = evidence

        if evidence["deck"]["total_cards"] == 0:
            result.warnings.append("No flashcards yet - generate a deck first.")
            result.recommendations = [
                {
                    "title": "Generate your first deck",
                    "detail": "Upload a document and run flashcard generation to start.",
                    "category": "setup",
                    "priority": 1,
                }
            ]
            return result

        try:
            result.recommendations = self._recommend(evidence, limit)
        except (LLMUnavailable, LLMInvalidOutput) as exc:
            result.warnings.append(f"LLM unavailable ({exc}); using rule-based advice.")
            result.recommendations = self._rule_based(evidence, limit)

        result.trace = self.trace.summary()
        return result

    # ------------------------------------------------------------- evidence

    def _gather_evidence(self) -> dict:
        performance = self.tools.topic_performance()
        due = self.tools.due_counts()

        recent_tests = (
            self.db.query(Test)
            .filter(Test.instance_id == self.instance_id, Test.score.isnot(None))
            .order_by(Test.completed_at.desc())
            .limit(5)
            .all()
        )

        # Coverage gap: topics present in the corpus that the deck never covers.
        chunk_count = (
            self.db.query(func.count(Chunk.id))
            .filter(Chunk.instance_id == self.instance_id)
            .scalar()
            or 0
        )
        covered_chunk_ids = set()
        for (chunk_ids,) in self.db.query(Flashcard.source_chunk_ids).filter(
            Flashcard.instance_id == self.instance_id
        ):
            if isinstance(chunk_ids, list):
                covered_chunk_ids.update(chunk_ids)

        card_topics = [
            row[0]
            for row in self.db.query(Flashcard.topic)
            .filter(
                Flashcard.instance_id == self.instance_id,
                Flashcard.topic.isnot(None),
            )
            .distinct()
            .all()
        ]

        return {
            "performance": performance[:10],
            "deck": {
                "total_cards": due["total"],
                "due_now": due["due"],
                "topics": card_topics[:20],
            },
            "coverage": {
                "chunks_total": int(chunk_count),
                "chunks_used_by_cards": len(covered_chunk_ids),
                "coverage_ratio": round(
                    len(covered_chunk_ids) / chunk_count, 3
                ) if chunk_count else 0.0,
            },
            "tests": [
                {
                    "score": test.score,
                    "questions": test.question_count,
                    "at": test.completed_at.isoformat() if test.completed_at else None,
                }
                for test in recent_tests
            ],
        }

    # ------------------------------------------------------------- LLM node

    def _recommend(self, evidence: dict, limit: int) -> List[dict]:
        prompt = f"""You are a study coach. Give this learner concrete next steps.

EVIDENCE (all numbers are measured, not estimated):
{json.dumps(evidence, ensure_ascii=False, indent=2)}

Write at most {limit} recommendations. Rules:
- Every recommendation must reference a specific number or topic from the
  EVIDENCE. Generic advice like "study regularly" is not acceptable.
- Be concrete about what to do next and why.
- "category" is one of: revision, coverage, testing, pacing.
- priority: 1 = do this first, 5 = optional.

Return ONLY a JSON object with a "recommendations" array:
{{
  "recommendations": [
    {{
      "title": "short actionable title",
      "detail": "what to do and why, citing the evidence",
      "category": "revision|coverage|testing|pacing",
      "priority": 1
    }}
  ]
}}"""

        recommendations = generate_json(
            prompt,
            schemas.validate_recommendations,
            node="recommender",
            trace=self.trace,
        )
        recommendations.sort(key=lambda item: item["priority"])
        return recommendations[:limit]

    # --------------------------------------------------------------- rules

    def _rule_based(self, evidence: dict, limit: int) -> List[dict]:
        recommendations = []

        due = evidence["deck"]["due_now"]
        if due > 0:
            recommendations.append(
                {
                    "title": f"Clear {due} due cards",
                    "detail": f"You have {due} cards scheduled for review today.",
                    "category": "revision",
                    "priority": 1,
                }
            )

        weak = [p for p in evidence["performance"] if p["accuracy"] < 0.6]
        for item in weak[:2]:
            recommendations.append(
                {
                    "title": f"Rebuild '{item['topic']}'",
                    "detail": (
                        f"Accuracy is {item['accuracy']:.0%} over {item['reviews']} "
                        f"reviews - the weakest topic in this instance."
                    ),
                    "category": "revision",
                    "priority": 2,
                }
            )

        coverage = evidence["coverage"]
        if coverage["chunks_total"] and coverage["coverage_ratio"] < 0.5:
            recommendations.append(
                {
                    "title": "Expand deck coverage",
                    "detail": (
                        f"Only {coverage['chunks_used_by_cards']} of "
                        f"{coverage['chunks_total']} source sections are covered by "
                        f"cards ({coverage['coverage_ratio']:.0%})."
                    ),
                    "category": "coverage",
                    "priority": 3,
                }
            )

        if not evidence["tests"]:
            recommendations.append(
                {
                    "title": "Take a baseline test",
                    "detail": "No test attempts recorded yet - a test calibrates which topics actually need work.",
                    "category": "testing",
                    "priority": 3,
                }
            )

        return recommendations[:limit]


def run_recommendation_agent(db: Session, instance_id: int, limit: int = 5) -> dict:
    return RecommendationAgent(db, instance_id).run(limit=limit).to_dict()
