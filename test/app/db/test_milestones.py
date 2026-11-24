from __future__ import annotations

from app.db.memory import upsert_state
from app.db.milestones import (
    create_milestone,
    get_introduced_counts_by_milestone,
    get_milestone,
    get_milestone_item_counts,
    list_milestones,
)
from app.db.models import UserItemState
from app.db.skills import create_skill_item
from app.db.users import create_user


def test__create_milestone_roundtrip_with_prerequisites() -> None:
    first = create_milestone("Classroom language", "Can follow a lesson", "A1")
    second = create_milestone("Greetings", "Can greet someone", "A1", prerequisite_ids=[first.id])

    assert second.prerequisite_ids == [first.id]
    assert get_milestone(second.id) == second


def test__get_milestone_missing_returns_none() -> None:
    assert get_milestone(999) is None


def test__list_milestones_is_language_independent() -> None:
    created = create_milestone("Greetings", "Can greet someone", "A1")

    roster = list_milestones()

    assert created.id in {m.id for m in roster}


def test__get_milestone_item_counts_counts_items_for_that_language_pair_only() -> None:
    milestone = create_milestone("Greetings", "Can greet someone", "A1")
    create_skill_item("vocab", "eng", "fra", "bonjour", milestone.id)
    create_skill_item("vocab", "eng", "fra", "salut", milestone.id)
    create_skill_item("vocab", "eng", "spa", "hola", milestone.id)

    assert get_milestone_item_counts("eng", "fra") == {milestone.id: 2}


def test__get_introduced_counts_by_milestone_counts_only_introduced_items() -> None:
    milestone = create_milestone("Greetings", "Can greet someone", "A1")
    introduced_item = create_skill_item("vocab", "eng", "fra", "bonjour", milestone.id)
    create_skill_item("vocab", "eng", "fra", "salut", milestone.id)  # never introduced
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    upsert_state(
        UserItemState(
            user_id=user.id,
            item_id=introduced_item.id,
            fsrs_card_json="{}",
            reps=1,
            lapses=0,
            last_reviewed_at=None,
            due_at="2099-01-01T00:00:00Z",
        )
    )

    assert get_introduced_counts_by_milestone(user.id, "eng", "fra") == {milestone.id: 1}
