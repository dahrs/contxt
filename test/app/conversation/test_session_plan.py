from __future__ import annotations

import pytest

import app.conversation.session_plan as session_plan_module
from app.config import settings
from app.conversation.session_plan import build_session_plan
from app.db.models import SkillItem, User, UserItemState


def _user() -> User:
    return User(
        id=1,
        username="alice",
        password_hash="x",
        display_name="Alice",
        native_lang="eng",
        target_lang="fra",
        is_absolute_beginner=False,
        email=None,
        last_proactive_sent_at=None,
        created_at="2026-01-01T00:00:00Z",
    )


def _item(id_: int, category: str | None = None) -> SkillItem:
    return SkillItem(
        id=id_,
        type="vocab",
        target_lang="fra",
        content=f"item-{id_}",
        level="A1",
        category=category,
        prerequisite_ids=[],
    )


def _state(item_id: int, due_at: str = "2020-01-01T00:00:00Z", lapses: int = 0) -> UserItemState:
    return UserItemState(
        user_id=1, item_id=item_id, fsrs_card_json="{}", reps=1, lapses=lapses, last_reviewed_at=None, due_at=due_at
    )


def _patch_collaborators(
    monkeypatch: pytest.MonkeyPatch,
    all_items: list[SkillItem],
    introduced_ids: set[int],
    due_states: list[UserItemState],
    mastered_states: list[UserItemState],
    chronic_states: list[UserItemState],
    interests: dict[str, float],
    recent_topics: list[str],
) -> None:
    monkeypatch.setattr(session_plan_module, "list_skill_items", lambda target_lang: all_items)
    monkeypatch.setattr(session_plan_module, "get_introduced_item_ids", lambda user_id: introduced_ids)
    monkeypatch.setattr(session_plan_module, "get_due_items", lambda user_id, now_iso: due_states)
    monkeypatch.setattr(session_plan_module, "get_mastered_states", lambda user_id, now_iso: mastered_states)
    monkeypatch.setattr(session_plan_module, "get_chronic_issue_states", lambda user_id: chronic_states)
    monkeypatch.setattr(session_plan_module, "get_interests", lambda user_id: interests)
    monkeypatch.setattr(session_plan_module, "get_recent_topics", lambda user_id: recent_topics)


def test__build_session_plan_separates_due_and_new_items(monkeypatch: pytest.MonkeyPatch) -> None:
    due_item = _item(1)
    new_item = _item(2)
    _patch_collaborators(
        monkeypatch,
        all_items=[due_item, new_item],
        introduced_ids={due_item.id},
        due_states=[_state(due_item.id)],
        mastered_states=[],
        chronic_states=[],
        interests={"travel": 1.0},
        recent_topics=[],
    )

    plan = build_session_plan(_user())

    assert [i.id for i in plan.due_items] == [due_item.id]
    assert [i.id for i in plan.new_items] == [new_item.id]
    assert plan.topic == "travel"


def test__build_session_plan_builds_learner_profile_from_mastered_and_chronic_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mastered_item = _item(1, category="greetings")
    chronic_item = _item(2, category="grammar")
    _patch_collaborators(
        monkeypatch,
        all_items=[mastered_item, chronic_item],
        introduced_ids={mastered_item.id, chronic_item.id},
        due_states=[],
        mastered_states=[_state(mastered_item.id)],
        chronic_states=[_state(chronic_item.id, lapses=3)],
        interests={"travel": 1.0},
        recent_topics=[],
    )

    plan = build_session_plan(_user())

    assert plan.learner_profile.known_item_count == 1
    assert plan.learner_profile.known_categories == {"greetings": 1}
    assert [i.id for i in plan.learner_profile.chronic_issue_items] == [chronic_item.id]


def test__build_session_plan_caps_due_items_so_a_long_gap_cant_flood_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    many_items = [_item(i) for i in range(1, settings.max_due_items_per_session + 5)]
    _patch_collaborators(
        monkeypatch,
        all_items=many_items,
        introduced_ids={item.id for item in many_items},
        due_states=[_state(item.id) for item in many_items],  # all overdue - e.g. after a long gap
        mastered_states=[],
        chronic_states=[],
        interests={"travel": 1.0},
        recent_topics=[],
    )

    plan = build_session_plan(_user())

    assert len(plan.due_items) == settings.max_due_items_per_session


def test__build_session_plan_caps_chronic_issue_items_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    many_items = [_item(i) for i in range(1, settings.max_chronic_items_shown + 5)]
    _patch_collaborators(
        monkeypatch,
        all_items=many_items,
        introduced_ids={item.id for item in many_items},
        due_states=[],
        mastered_states=[],
        chronic_states=[_state(item.id, lapses=5) for item in many_items],
        interests={"travel": 1.0},
        recent_topics=[],
    )

    plan = build_session_plan(_user())

    assert len(plan.learner_profile.chronic_issue_items) == settings.max_chronic_items_shown
