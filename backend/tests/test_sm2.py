"""Unit tests for the SM-2 scheduler, including the bugs it replaced."""

from backend.src.ai.scheduling import sm2
from backend.src.ai.scheduling.sm2 import SchedulerState, quality_from_bool, review


def test_first_two_intervals_are_fixed():
    state = SchedulerState()

    first = review(state, quality_from_bool(True))
    assert first.repetitions == 1
    assert first.interval == sm2.FIRST_INTERVAL

    second = review(
        SchedulerState(repetitions=first.repetitions, interval=first.interval,
                       ease_factor=first.ease_factor),
        quality_from_bool(True),
    )
    assert second.repetitions == 2
    assert second.interval == sm2.SECOND_INTERVAL


def test_interval_grows_by_ease_after_second_review():
    state = SchedulerState(repetitions=2, interval=6, ease_factor=2.5)
    update = review(state, quality_from_bool(True))
    assert update.interval == round(6 * update.ease_factor)
    assert update.interval > 6


def test_ease_never_exceeds_ceiling():
    """The old code did ease += 0.1 forever, so intervals exploded."""
    state = SchedulerState(repetitions=5, interval=30, ease_factor=2.5)

    for _ in range(50):
        update = review(state, 5)
        state = SchedulerState(
            repetitions=update.repetitions,
            interval=update.interval,
            ease_factor=update.ease_factor,
            lapses=update.lapses,
        )

    assert state.ease_factor <= sm2.MAX_EASE


def test_ease_never_falls_below_floor():
    state = SchedulerState(repetitions=3, interval=10, ease_factor=1.4)

    for _ in range(20):
        update = review(state, 0)
        state = SchedulerState(
            repetitions=update.repetitions,
            interval=update.interval,
            ease_factor=update.ease_factor,
            lapses=update.lapses,
        )

    assert state.ease_factor >= sm2.MIN_EASE


def test_lapse_preserves_ease():
    """The old code reset ease to 2.5 on failure, discarding card difficulty."""
    state = SchedulerState(repetitions=4, interval=40, ease_factor=1.7)
    update = review(state, quality_from_bool(False))

    assert update.repetitions == 0
    assert update.interval == sm2.FIRST_INTERVAL
    assert update.lapses == 1
    assert update.ease_factor < 2.5  # kept and decreased, not reset upward


def test_low_ease_interval_does_not_stall():
    """int() truncation kept interval=1 * ease=1.3 pinned at 1 forever."""
    state = SchedulerState(repetitions=2, interval=1, ease_factor=1.3)
    update = review(state, quality_from_bool(True))
    assert update.interval > 1


def test_interval_is_capped():
    state = SchedulerState(repetitions=10, interval=300, ease_factor=3.0)
    update = review(state, 5)
    assert update.interval <= sm2.MAX_INTERVAL


def test_next_review_matches_interval():
    from datetime import datetime

    now = datetime(2026, 1, 1)
    update = review(SchedulerState(), quality_from_bool(True), now=now)
    assert (update.next_review - now).days == update.interval
