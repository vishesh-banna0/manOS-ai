"""
File: sm2.py

Purpose:
SM-2 spaced repetition, as pure functions.

Kept free of SQLAlchemy so the scheduler can be unit-tested and simulated by
the evaluation harness without a database.

Fixes over the previous inline implementation in flashcard_service:
- Ease factor was incremented by a flat +0.1 on every success with no ceiling,
  so intervals grew without bound; SM-2 adjusts ease by recall quality and
  floors it at 1.3.
- A lapse reset ease_factor to 2.5, discarding everything learned about how
  hard that card is for this user; SM-2 keeps ease across lapses.
- `interval = int(interval * ease)` truncated toward zero, so an interval of 1
  with ease 1.3 stayed at 1 forever.
- Fixed first/second intervals (1 day, 6 days) were missing entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

MIN_EASE = 1.3
MAX_EASE = 3.0
PASS_THRESHOLD = 3  # SM-2: quality >= 3 counts as recalled

FIRST_INTERVAL = 1
SECOND_INTERVAL = 6
MAX_INTERVAL = 365


@dataclass
class SchedulerState:
    """Scheduler state for one card."""

    repetitions: int = 0
    interval: int = 0
    ease_factor: float = 2.5
    lapses: int = 0


@dataclass
class SchedulerUpdate:
    """Result of grading a review."""

    repetitions: int
    interval: int
    ease_factor: float
    lapses: int
    next_review: datetime
    lapsed: bool


def quality_from_bool(correct: bool) -> int:
    """
    Map a binary answer onto the SM-2 0-5 scale.

    The UI only reports correct/incorrect, so 4 ("correct after hesitation")
    and 2 ("incorrect but familiar") are the honest midpoints - claiming 5 or 0
    would overstate what the interface actually measured.
    """
    return 4 if correct else 2


def update_ease(ease: float, quality: int) -> float:
    """Standard SM-2 ease adjustment, clamped to a sane band."""
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    return max(MIN_EASE, min(MAX_EASE, ease + delta))


def review(
    state: SchedulerState,
    quality: int,
    now: Optional[datetime] = None,
) -> SchedulerUpdate:
    """
    Grade a review and produce the next scheduler state.

    Args:
        state: current card state
        quality: recall quality 0-5
        now: injectable clock (the effectiveness simulation runs on fake time)
    """
    now = now or datetime.utcnow()
    quality = max(0, min(5, int(quality)))

    ease = update_ease(state.ease_factor, quality)
    passed = quality >= PASS_THRESHOLD

    if passed:
        repetitions = state.repetitions + 1
        lapses = state.lapses

        if repetitions == 1:
            interval = FIRST_INTERVAL
        elif repetitions == 2:
            interval = SECOND_INTERVAL
        else:
            # Two guards here, both needed:
            # - round() not int(): truncation loses a day on every step.
            # - the +1 floor: at low ease, round(1 * 1.3) == 1, so a card
            #   would repeat at a one-day interval forever. Reachable for rows
            #   migrated from the legacy scheduler, which defaulted interval
            #   to 1 at any repetition count. A passed review must always push
            #   the card further out.
            interval = max(state.interval + 1, round(state.interval * ease))

        interval = min(interval, MAX_INTERVAL)
    else:
        # Lapse: relearn from the start but KEEP the ease we have learned.
        repetitions = 0
        interval = FIRST_INTERVAL
        lapses = state.lapses + 1

    return SchedulerUpdate(
        repetitions=repetitions,
        interval=interval,
        ease_factor=round(ease, 4),
        lapses=lapses,
        next_review=now + timedelta(days=interval),
        lapsed=not passed,
    )
