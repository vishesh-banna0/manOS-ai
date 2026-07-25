"""
File: analytics_service.py

Purpose:
Performance analytics backing GET /instances/{id}/analytics.

The Analytics page previously read from an empty client-side store, so every
chart rendered blank. These aggregates come from the review log and test
history, which is also what the revision and recommendation agents consume -
one source of truth for "how is this learner doing".
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from ..models.chunk import Chunk
from ..models.flashcard import Flashcard
from ..models.review_log import ReviewLog
from ..models.test import Test

WEAK_ACCURACY = 0.6


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_analytics(self, instance_id: int, days: int = 30) -> Dict:
        cutoff = datetime.utcnow() - timedelta(days=days)

        return {
            "instance_id": instance_id,
            "window_days": days,
            "summary": self._summary(instance_id, cutoff),
            "accuracy_over_time": self._accuracy_over_time(instance_id, cutoff),
            "topic_performance": self._topic_performance(instance_id, cutoff),
            "weak_areas": self._weak_areas(instance_id, cutoff),
            "difficulty_breakdown": self._difficulty_breakdown(instance_id, cutoff),
            "schedule": self._schedule(instance_id),
            "tests": self._tests(instance_id),
            "coverage": self._coverage(instance_id),
        }

    # -------------------------------------------------------------- sections

    def _summary(self, instance_id: int, cutoff: datetime) -> Dict:
        total_reviews, correct_reviews = self._review_totals(instance_id, cutoff)

        total_cards = (
            self.db.query(func.count(Flashcard.id))
            .filter(Flashcard.instance_id == instance_id)
            .scalar()
            or 0
        )
        due_now = (
            self.db.query(func.count(Flashcard.id))
            .filter(
                Flashcard.instance_id == instance_id,
                Flashcard.next_review <= datetime.utcnow(),
                Flashcard.suspended.is_(False),
            )
            .scalar()
            or 0
        )
        mature = (
            self.db.query(func.count(Flashcard.id))
            .filter(Flashcard.instance_id == instance_id, Flashcard.interval >= 21)
            .scalar()
            or 0
        )

        return {
            "total_cards": int(total_cards),
            "due_now": int(due_now),
            "mature_cards": int(mature),
            "total_reviews": total_reviews,
            "correct_reviews": correct_reviews,
            "avg_accuracy": round(correct_reviews / total_reviews, 4) if total_reviews else None,
            "retention_rate": round(correct_reviews / total_reviews, 4) if total_reviews else None,
        }

    def _review_totals(self, instance_id: int, cutoff: datetime) -> tuple[int, int]:
        row = (
            self.db.query(
                func.count(ReviewLog.id),
                func.sum(func.cast(ReviewLog.correct, Integer)),
            )
            .filter(
                ReviewLog.instance_id == instance_id,
                ReviewLog.reviewed_at >= cutoff,
            )
            .first()
        )
        total = int(row[0] or 0)
        correct = int(row[1] or 0)
        return total, correct

    def _accuracy_over_time(self, instance_id: int, cutoff: datetime) -> List[Dict]:
        rows = (
            self.db.query(
                func.date(ReviewLog.reviewed_at).label("day"),
                func.count(ReviewLog.id).label("reviews"),
                func.sum(func.cast(ReviewLog.correct, Integer)).label("correct"),
            )
            .filter(
                ReviewLog.instance_id == instance_id,
                ReviewLog.reviewed_at >= cutoff,
            )
            .group_by(func.date(ReviewLog.reviewed_at))
            .order_by(func.date(ReviewLog.reviewed_at))
            .all()
        )

        series = []
        for day, reviews, correct in rows:
            reviews = int(reviews or 0)
            if not reviews:
                continue
            series.append(
                {
                    "date": day.isoformat() if hasattr(day, "isoformat") else str(day),
                    "reviews": reviews,
                    # Percentage - the chart's Y axis is 0-100.
                    "accuracy": round(int(correct or 0) / reviews * 100, 1),
                }
            )

        return series

    def _topic_performance(self, instance_id: int, cutoff: datetime) -> List[Dict]:
        rows = (
            self.db.query(
                ReviewLog.topic,
                func.count(ReviewLog.id),
                func.sum(func.cast(ReviewLog.correct, Integer)),
            )
            .filter(
                ReviewLog.instance_id == instance_id,
                ReviewLog.reviewed_at >= cutoff,
                ReviewLog.topic.isnot(None),
            )
            .group_by(ReviewLog.topic)
            .all()
        )

        performance = []
        for topic, reviews, correct in rows:
            reviews = int(reviews or 0)
            if not reviews:
                continue
            performance.append(
                {
                    "topic": topic,
                    "totalQuestions": reviews,
                    "correct": int(correct or 0),
                    "accuracy": round(int(correct or 0) / reviews * 100, 1),
                }
            )

        performance.sort(key=lambda item: item["accuracy"], reverse=True)
        return performance

    def _weak_areas(self, instance_id: int, cutoff: datetime) -> List[str]:
        return [
            item["topic"]
            for item in self._topic_performance(instance_id, cutoff)
            if item["accuracy"] < WEAK_ACCURACY * 100 and item["totalQuestions"] >= 2
        ]

    def _difficulty_breakdown(self, instance_id: int, cutoff: datetime) -> List[Dict]:
        rows = (
            self.db.query(
                ReviewLog.difficulty,
                func.count(ReviewLog.id),
                func.sum(func.cast(ReviewLog.correct, Integer)),
            )
            .filter(
                ReviewLog.instance_id == instance_id,
                ReviewLog.reviewed_at >= cutoff,
                ReviewLog.difficulty.isnot(None),
            )
            .group_by(ReviewLog.difficulty)
            .all()
        )

        breakdown = []
        for difficulty, reviews, correct in rows:
            reviews = int(reviews or 0)
            if not reviews:
                continue
            breakdown.append(
                {
                    "difficulty": difficulty,
                    "reviews": reviews,
                    "accuracy": round(int(correct or 0) / reviews * 100, 1),
                }
            )

        order = {"easy": 0, "medium": 1, "hard": 2}
        breakdown.sort(key=lambda item: order.get(item["difficulty"], 9))
        return breakdown

    def _schedule(self, instance_id: int) -> Dict:
        """Upcoming review load - how many cards fall due over the next week."""
        now = datetime.utcnow()
        upcoming = []

        for offset in range(0, 7):
            start = now + timedelta(days=offset)
            end = now + timedelta(days=offset + 1)
            count = (
                self.db.query(func.count(Flashcard.id))
                .filter(
                    Flashcard.instance_id == instance_id,
                    Flashcard.next_review >= start,
                    Flashcard.next_review < end,
                    Flashcard.suspended.is_(False),
                )
                .scalar()
                or 0
            )
            upcoming.append({"date": (now + timedelta(days=offset)).date().isoformat(),
                             "due": int(count)})

        avg_interval = (
            self.db.query(func.avg(Flashcard.interval))
            .filter(Flashcard.instance_id == instance_id, Flashcard.repetitions > 0)
            .scalar()
        )
        avg_ease = (
            self.db.query(func.avg(Flashcard.ease_factor))
            .filter(Flashcard.instance_id == instance_id)
            .scalar()
        )

        return {
            "upcoming": upcoming,
            "avg_interval_days": round(float(avg_interval), 2) if avg_interval else 0.0,
            "avg_ease_factor": round(float(avg_ease), 3) if avg_ease else 0.0,
        }

    def _tests(self, instance_id: int) -> List[Dict]:
        rows = (
            self.db.query(Test)
            .filter(Test.instance_id == instance_id, Test.score.isnot(None))
            .order_by(Test.completed_at.desc())
            .limit(10)
            .all()
        )
        return [
            {
                "test_id": test.id,
                "score": test.score,
                "questions": test.question_count,
                "completed_at": test.completed_at.isoformat() if test.completed_at else None,
            }
            for test in rows
        ]

    def _coverage(self, instance_id: int) -> Dict:
        """How much of the indexed corpus the deck actually covers."""
        chunk_count = (
            self.db.query(func.count(Chunk.id))
            .filter(Chunk.instance_id == instance_id)
            .scalar()
            or 0
        )

        covered = set()
        for (chunk_ids,) in self.db.query(Flashcard.source_chunk_ids).filter(
            Flashcard.instance_id == instance_id
        ):
            if isinstance(chunk_ids, list):
                covered.update(chunk_ids)

        return {
            "chunks_total": int(chunk_count),
            "chunks_covered": len(covered),
            "coverage_ratio": round(len(covered) / chunk_count, 3) if chunk_count else 0.0,
        }
