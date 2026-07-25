"""
File: learning_eval.py

Purpose:
Measure learning effectiveness - does the scheduler actually help?

Two modes:

1. SIMULATION. A synthetic learner with per-card memory strength studies a deck
   under different schedulers over simulated time. Recall probability follows
   an exponential forgetting curve: p = exp(-elapsed / stability), with
   stability growing on each success. Because the learner model is identical
   across schedulers, differences in the results are attributable to the
   scheduling policy.

   Schedulers compared:
   - sm2         : the shipped implementation
   - legacy_buggy: the previous inline logic (ease += 0.1 unbounded, ease reset
                   to 2.5 on lapse, int() truncation) - present so the fix is
                   demonstrated rather than asserted
   - fixed_1day  : review everything every day (upper bound on retention,
                   worst possible efficiency)

   The headline metric is retention per review: a scheduler that shows you
   every card daily gets high retention by brute force, which is not learning
   efficiency.

2. REAL DATA. The same effectiveness metrics computed from ReviewLog rows for
   an instance, once a learner has actually used it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from ..src.ai.scheduling.sm2 import SchedulerState, quality_from_bool
from ..src.ai.scheduling.sm2 import review as sm2_review
from ..src.models.flashcard import Flashcard
from ..src.models.review_log import ReviewLog

# Simulation constants
INITIAL_STABILITY_DAYS = 1.0
STABILITY_GROWTH = 1.9
STABILITY_ON_LAPSE = 0.6
MASTERY_STABILITY_DAYS = 21.0


@dataclass
class SimCard:
    """A card in the simulation, with the learner's true memory of it."""

    card_id: int
    difficulty: float  # 0-1; higher means harder to retain
    stability: float = INITIAL_STABILITY_DAYS
    last_seen: float = 0.0  # simulated day
    state: SchedulerState = field(default_factory=SchedulerState)
    due_day: float = 0.0
    reviews: int = 0
    successes: int = 0

    def recall_probability(self, day: float) -> float:
        """Exponential forgetting curve."""
        elapsed = max(0.0, day - self.last_seen)
        effective_stability = max(0.1, self.stability * (1.0 - 0.5 * self.difficulty))
        return math.exp(-elapsed / effective_stability)


def _legacy_schedule(state: SchedulerState, correct: bool) -> SchedulerState:
    """
    The scheduler this project used before SM-2.

    Reproduced faithfully, bugs included: unbounded ease growth, ease reset on
    failure, and int() truncation of the interval.
    """
    if correct:
        repetitions = state.repetitions + 1
        interval = int(state.interval * state.ease_factor)
        ease = state.ease_factor + 0.1
        lapses = state.lapses
    else:
        repetitions = 0
        interval = 1
        ease = 2.5
        lapses = state.lapses + 1

    return SchedulerState(
        repetitions=repetitions,
        interval=max(1, interval),
        ease_factor=ease,
        lapses=lapses,
    )


def simulate(
    scheduler: str,
    deck_size: int = 60,
    days: int = 120,
    daily_review_limit: int = 40,
    seed: int = 7,
) -> Dict:
    """
    Run one scheduler over a synthetic learner and deck.

    Returns retention, efficiency and mastery metrics.
    """
    rng = random.Random(seed)

    cards = [
        SimCard(
            card_id=index,
            difficulty=rng.betavariate(2, 5),  # most cards easy-ish, some hard
            state=SchedulerState(interval=0 if scheduler != "legacy_buggy" else 1),
        )
        for index in range(deck_size)
    ]

    total_reviews = 0
    total_successes = 0
    retention_samples: List[float] = []

    for day in range(days):
        due = [card for card in cards if card.due_day <= day][:daily_review_limit]

        for card in due:
            # Did the learner recall it? Sampled from their true memory state.
            probability = card.recall_probability(day)
            correct = rng.random() < probability

            total_reviews += 1
            card.reviews += 1
            retention_samples.append(1.0 if correct else 0.0)
            if correct:
                total_successes += 1
                card.successes += 1

            # Update the learner's memory.
            if correct:
                card.stability *= STABILITY_GROWTH
            else:
                card.stability = max(INITIAL_STABILITY_DAYS, card.stability * STABILITY_ON_LAPSE)
            card.last_seen = day

            # Update the schedule.
            if scheduler == "fixed_1day":
                card.due_day = day + 1
            elif scheduler == "legacy_buggy":
                card.state = _legacy_schedule(card.state, correct)
                card.due_day = day + card.state.interval
            else:  # sm2
                update = sm2_review(card.state, quality_from_bool(correct))
                card.state = SchedulerState(
                    repetitions=update.repetitions,
                    interval=update.interval,
                    ease_factor=update.ease_factor,
                    lapses=update.lapses,
                )
                card.due_day = day + update.interval

    # --- final knowledge check: probability of recall at the end ---
    final_recall = [card.recall_probability(days) for card in cards]
    mastered = sum(1 for card in cards if card.stability >= MASTERY_STABILITY_DAYS)

    # Starvation: under a fixed daily budget, a scheduler that keeps re-queuing
    # the same cards can leave part of the deck never studied. Reporting this
    # explains otherwise-confusing recall numbers.
    never_reviewed = sum(1 for card in cards if card.reviews == 0)

    retention = total_successes / total_reviews if total_reviews else 0.0
    avg_interval = (
        sum(card.state.interval for card in cards) / len(cards) if cards else 0.0
    )

    return {
        "scheduler": scheduler,
        "days_simulated": days,
        "deck_size": deck_size,
        "daily_review_limit": daily_review_limit,
        "total_reviews": total_reviews,
        "review_retention": round(retention, 4),
        "final_recall_mean": round(sum(final_recall) / len(final_recall), 4),
        "cards_mastered": mastered,
        "mastery_rate": round(mastered / len(cards), 4),
        "cards_never_reviewed": never_reviewed,
        "deck_coverage": round(1 - never_reviewed / len(cards), 4),
        # The efficiency metric: end-state knowledge bought per review.
        "recall_per_review": round(
            (sum(final_recall) / len(final_recall)) / (total_reviews / len(cards)), 5
        )
        if total_reviews
        else 0.0,
        "reviews_per_card": round(total_reviews / len(cards), 2),
        "avg_final_interval_days": round(avg_interval, 2),
        "total_lapses": sum(card.state.lapses for card in cards),
    }


def run_simulation_comparison(
    deck_size: int = 60, days: int = 120, seed: int = 7
) -> Dict:
    """Compare all schedulers on an identical learner and deck."""
    schedulers = ["sm2", "legacy_buggy", "fixed_1day"]
    results = {
        name: simulate(name, deck_size=deck_size, days=days, seed=seed)
        for name in schedulers
    }

    sm2_result = results["sm2"]
    legacy = results["legacy_buggy"]
    fixed = results["fixed_1day"]

    # Interpretation is derived from the numbers, not asserted ahead of them.
    notes = [
        "review_retention is in-session accuracy; final_recall_mean is modelled "
        "recall of the whole deck at the end. They diverge on purpose - drilling "
        "easy cards daily inflates the first while doing little for the second.",
    ]

    if fixed["cards_never_reviewed"] > 0:
        notes.append(
            f"fixed_1day never reached {fixed['cards_never_reviewed']} of "
            f"{fixed['deck_size']} cards: re-queuing everything daily exceeds the "
            f"{fixed['daily_review_limit']}/day budget, so the tail of the deck "
            f"starves. Its high review_retention ({fixed['review_retention']}) is "
            f"measured only on the cards it kept showing."
        )

    if sm2_result["recall_per_review"] > legacy["recall_per_review"]:
        notes.append(
            f"SM-2 buys more retained knowledge per review than the legacy "
            f"scheduler ({sm2_result['recall_per_review']} vs "
            f"{legacy['recall_per_review']}) while issuing "
            f"{legacy['total_reviews'] - sm2_result['total_reviews']} fewer reviews."
        )

    return {
        "results": results,
        "comparison": {
            "sm2_vs_legacy_final_recall": round(
                sm2_result["final_recall_mean"] - legacy["final_recall_mean"], 4
            ),
            "sm2_vs_legacy_reviews": sm2_result["total_reviews"] - legacy["total_reviews"],
            "sm2_vs_legacy_recall_per_review": round(
                sm2_result["recall_per_review"] - legacy["recall_per_review"], 5
            ),
            "sm2_vs_fixed_reviews_saved": fixed["total_reviews"] - sm2_result["total_reviews"],
            "sm2_vs_fixed_deck_coverage": round(
                sm2_result["deck_coverage"] - fixed["deck_coverage"], 4
            ),
        },
        "interpretation": " ".join(notes),
    }


def evaluate_real_learning(db: Session, instance_id: int, days: int = 90) -> Dict:
    """Effectiveness metrics from a real learner's review history."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    logs = (
        db.query(ReviewLog)
        .filter(ReviewLog.instance_id == instance_id, ReviewLog.reviewed_at >= cutoff)
        .order_by(ReviewLog.reviewed_at)
        .all()
    )

    if not logs:
        return {
            "reviews": 0,
            "note": "No review history yet - effectiveness cannot be measured.",
        }

    correct = sum(1 for log in logs if log.correct)
    retention = correct / len(logs)

    # Retention split by how long the card had been waiting: if long intervals
    # retain as well as short ones, the scheduler is spacing well.
    short, long = [], []
    for log in logs:
        bucket = short if (log.interval_before or 0) <= 3 else long
        bucket.append(1 if log.correct else 0)

    # Improvement over time: first third vs last third of the history.
    third = max(1, len(logs) // 3)
    early = logs[:third]
    late = logs[-third:]

    cards = db.query(Flashcard).filter(Flashcard.instance_id == instance_id).all()
    mature = sum(1 for card in cards if (card.interval or 0) >= 21)

    avg_ease = (
        db.query(func.avg(Flashcard.ease_factor))
        .filter(Flashcard.instance_id == instance_id)
        .scalar()
    )
    lapse_total = (
        db.query(func.sum(func.cast(Flashcard.lapses, Integer)))
        .filter(Flashcard.instance_id == instance_id)
        .scalar()
        or 0
    )

    return {
        "reviews": len(logs),
        "window_days": days,
        "retention_rate": round(retention, 4),
        "retention_short_interval": round(sum(short) / len(short), 4) if short else None,
        "retention_long_interval": round(sum(long) / len(long), 4) if long else None,
        "retention_early": round(sum(1 for l in early if l.correct) / len(early), 4),
        "retention_late": round(sum(1 for l in late if l.correct) / len(late), 4),
        "retention_improvement": round(
            sum(1 for l in late if l.correct) / len(late)
            - sum(1 for l in early if l.correct) / len(early),
            4,
        ),
        "cards_total": len(cards),
        "cards_mature": mature,
        "mastery_rate": round(mature / len(cards), 4) if cards else 0.0,
        "avg_ease_factor": round(float(avg_ease), 3) if avg_ease else None,
        "total_lapses": int(lapse_total),
        "reviews_per_card": round(len(logs) / len(cards), 2) if cards else 0.0,
    }
