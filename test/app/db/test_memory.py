from __future__ import annotations

from app.db.memory import (
    get_chronic_issue_states,
    get_due_items,
    get_introduced_item_ids,
    get_mastered_states,
    get_state,
    upsert_state,
)
from app.db.models import UserItemState
from app.db.skills import create_skill_item
from app.db.users import create_user


def _state(user_id: int, item_id: int, *, due_at: str, lapses: int = 0, reps: int = 1) -> UserItemState:
    return UserItemState(
        user_id=user_id,
        item_id=item_id,
        fsrs_card_json="{}",
        reps=reps,
        lapses=lapses,
        last_reviewed_at="2026-01-01T00:00:00Z",
        due_at=due_at,
    )


def test__get_state_missing_returns_none() -> None:
    assert get_state(1, 1) is None


def test__upsert_state_insert_then_update() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    item = create_skill_item("vocab", "fra", "bonjour", "A1")

    upsert_state(_state(user.id, item.id, due_at="2026-01-01T00:00:00Z", reps=1))
    upsert_state(_state(user.id, item.id, due_at="2026-02-01T00:00:00Z", reps=2, lapses=1))

    state = get_state(user.id, item.id)
    assert state is not None
    assert state.reps == 2
    assert state.lapses == 1
    assert state.due_at == "2026-02-01T00:00:00Z"


def test__get_due_items_only_returns_items_due_by_given_time() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    due_item = create_skill_item("vocab", "fra", "bonjour", "A1")
    future_item = create_skill_item("vocab", "fra", "merci", "A1")
    upsert_state(_state(user.id, due_item.id, due_at="2026-01-01T00:00:00Z"))
    upsert_state(_state(user.id, future_item.id, due_at="2099-01-01T00:00:00Z"))

    due = get_due_items(user.id, "2026-06-01T00:00:00Z")

    assert [s.item_id for s in due] == [due_item.id]


def test__get_introduced_item_ids_reflects_all_states_regardless_of_due_date() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    item = create_skill_item("vocab", "fra", "bonjour", "A1")
    upsert_state(_state(user.id, item.id, due_at="2099-01-01T00:00:00Z"))

    assert get_introduced_item_ids(user.id) == {item.id}


def test__get_mastered_states_excludes_items_currently_due() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    mastered_item = create_skill_item("vocab", "fra", "bonjour", "A1")
    due_item = create_skill_item("vocab", "fra", "merci", "A1")
    upsert_state(_state(user.id, mastered_item.id, due_at="2099-01-01T00:00:00Z"))
    upsert_state(_state(user.id, due_item.id, due_at="2020-01-01T00:00:00Z"))

    mastered = get_mastered_states(user.id, "2026-06-01T00:00:00Z")

    assert [s.item_id for s in mastered] == [mastered_item.id]


def test__get_chronic_issue_states_filters_by_lapse_threshold() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    chronic_item = create_skill_item("vocab", "fra", "bonjour", "A1")
    fine_item = create_skill_item("vocab", "fra", "merci", "A1")
    upsert_state(_state(user.id, chronic_item.id, due_at="2099-01-01T00:00:00Z", lapses=3))
    upsert_state(_state(user.id, fine_item.id, due_at="2099-01-01T00:00:00Z", lapses=1))

    chronic = get_chronic_issue_states(user.id, lapse_threshold=2)

    assert [s.item_id for s in chronic] == [chronic_item.id]
