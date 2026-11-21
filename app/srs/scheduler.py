from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fsrs import Card, Rating, Scheduler

from app.db.models import UserItemState

MemoryRating = Literal["again", "hard", "good", "easy"]

_RATING_BY_NAME: dict[MemoryRating, Rating] = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
}

_scheduler = Scheduler()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def introduce(user_id: int, item_id: int) -> UserItemState:
    """Create the initial memory state for an item the user has never seen before."""
    card = Card()
    return UserItemState(
        user_id=user_id,
        item_id=item_id,
        fsrs_card_json=card.to_json(),
        reps=0,
        lapses=0,
        last_reviewed_at=None,
        due_at=card.due.isoformat(),
    )


def review(state: UserItemState, rating: MemoryRating) -> UserItemState:
    """Apply one review outcome to an item's memory state, advancing its FSRS schedule."""
    card = Card.from_json(state.fsrs_card_json)
    now = _utc_now()
    updated_card, _log = _scheduler.review_card(card, _RATING_BY_NAME[rating], now)
    return state.model_copy(
        update={
            "fsrs_card_json": updated_card.to_json(),
            "reps": state.reps + 1,
            "lapses": state.lapses + (1 if rating == "again" else 0),
            "last_reviewed_at": now.isoformat(),
            "due_at": updated_card.due.isoformat(),
        }
    )


def is_due(state: UserItemState, as_of: datetime | None = None) -> bool:
    as_of = as_of or _utc_now()
    return datetime.fromisoformat(state.due_at) <= as_of
