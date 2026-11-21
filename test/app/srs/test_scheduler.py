from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.srs.scheduler import introduce, is_due, review


def test__introduce_creates_fresh_unreviewed_state() -> None:
    state = introduce(user_id=1, item_id=1)

    assert state.reps == 0
    assert state.lapses == 0
    assert state.last_reviewed_at is None


def test__review_again_increments_lapses_and_reps() -> None:
    state = introduce(user_id=1, item_id=1)

    updated = review(state, "again")

    assert updated.reps == 1
    assert updated.lapses == 1
    assert updated.last_reviewed_at is not None


def test__review_good_increments_reps_without_a_lapse() -> None:
    state = introduce(user_id=1, item_id=1)

    updated = review(state, "good")

    assert updated.reps == 1
    assert updated.lapses == 0


def test__review_easy_pushes_due_date_further_than_again() -> None:
    state = introduce(user_id=1, item_id=1)

    easy = review(state, "easy")
    again = review(state, "again")

    assert datetime.fromisoformat(easy.due_at) > datetime.fromisoformat(again.due_at)


def test__is_due_true_for_past_due_date_false_for_future() -> None:
    now = datetime.now(UTC)
    past = introduce(user_id=1, item_id=1).model_copy(update={"due_at": (now - timedelta(days=1)).isoformat()})
    future = introduce(user_id=1, item_id=1).model_copy(update={"due_at": (now + timedelta(days=1)).isoformat()})

    assert is_due(past, as_of=now) is True
    assert is_due(future, as_of=now) is False
