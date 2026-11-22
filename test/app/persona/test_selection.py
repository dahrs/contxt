from __future__ import annotations

from datetime import UTC, datetime

import pytest

import app.persona.selection as selection_module
from app.db.models import Conversation, Persona, User
from app.persona.selection import (
    is_first_conversation,
    is_free_now,
    select_persona,
    select_proactive_persona,
    shared_interest,
)


def _user(is_absolute_beginner: bool = False) -> User:
    return User(
        id=1,
        username="alice",
        password_hash="x",
        display_name="Alice",
        native_lang="eng",
        target_lang="fra",
        is_absolute_beginner=is_absolute_beginner,
        email=None,
        last_proactive_sent_at=None,
        created_at="2026-01-01T00:00:00Z",
    )


def _persona(id_: int, interests: list[str] | None = None, free_hours: list[int] | None = None) -> Persona:
    return Persona(
        id=id_,
        target_lang="fra",
        name=f"persona-{id_}",
        origin="N/A",
        age=30,
        background="N/A",
        physical_description="N/A",
        psychological_profile="N/A",
        social_habits="N/A",
        explanation_style="N/A",
        teaching_philosophy="N/A",
        correction_style="N/A",
        preferred_medium="N/A",
        vocabulary_strictness="N/A",
        cultural_depth="N/A",
        timezone="UTC",
        daily_routine="N/A",
        free_hours=free_hours if free_hours is not None else list(range(24)),
        is_beginner_teacher=False,
        interests=interests or [],
    )


def _conversation() -> Conversation:
    return Conversation(
        id=1,
        user_id=1,
        persona_id=1,
        topic="travel",
        claude_session_id=None,
        target_item_ids=[],
        is_proactive=False,
        started_at="x",
    )


def test__is_first_conversation_true_when_none_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [])

    assert is_first_conversation(_user()) is True


def test__is_first_conversation_false_when_one_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [_conversation()])

    assert is_first_conversation(_user()) is False


def test__select_persona_routes_absolute_beginner_first_conversation_to_beginner_teacher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    beginner_teacher = _persona(99)
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [])
    monkeypatch.setattr(selection_module, "get_beginner_teacher_persona", lambda target_lang: beginner_teacher)

    assert select_persona(_user(is_absolute_beginner=True)) == beginner_teacher


def test__select_persona_falls_back_to_roster_when_no_beginner_teacher_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    roster_persona = _persona(1)
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [])
    monkeypatch.setattr(selection_module, "get_beginner_teacher_persona", lambda target_lang: None)
    monkeypatch.setattr(selection_module, "list_personas", lambda target_lang: [roster_persona])
    monkeypatch.setattr(selection_module, "get_most_recent_persona_id", lambda user_id: None)

    assert select_persona(_user(is_absolute_beginner=True)) == roster_persona


def test__select_persona_non_beginner_ignores_beginner_teacher_entirely(monkeypatch: pytest.MonkeyPatch) -> None:
    roster_persona = _persona(1)
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [])
    monkeypatch.setattr(selection_module, "list_personas", lambda target_lang: [roster_persona])
    monkeypatch.setattr(selection_module, "get_most_recent_persona_id", lambda user_id: None)

    def fail_if_called(target_lang: str) -> Persona | None:
        raise AssertionError("beginner-teacher lookup should not happen for a non-beginner")

    monkeypatch.setattr(selection_module, "get_beginner_teacher_persona", fail_if_called)

    assert select_persona(_user(is_absolute_beginner=False)) == roster_persona


def test__select_persona_raises_when_roster_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [])
    monkeypatch.setattr(selection_module, "list_personas", lambda target_lang: [])
    monkeypatch.setattr(selection_module, "get_most_recent_persona_id", lambda user_id: None)

    with pytest.raises(ValueError):
        select_persona(_user())


def test__select_persona_excludes_most_recently_used_persona(monkeypatch: pytest.MonkeyPatch) -> None:
    recent, other = _persona(1), _persona(2)
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [])
    monkeypatch.setattr(selection_module, "list_personas", lambda target_lang: [recent, other])
    monkeypatch.setattr(selection_module, "get_most_recent_persona_id", lambda user_id: recent.id)

    assert select_persona(_user()) == other


def test__select_persona_falls_back_to_full_roster_if_only_candidate_is_most_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_persona = _persona(1)
    monkeypatch.setattr(selection_module, "list_conversations", lambda user_id: [])
    monkeypatch.setattr(selection_module, "list_personas", lambda target_lang: [only_persona])
    monkeypatch.setattr(selection_module, "get_most_recent_persona_id", lambda user_id: only_persona.id)

    assert select_persona(_user()) == only_persona


def test__shared_interest_prefers_genuine_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "sensitive_topics", lambda: frozenset())
    persona = _persona(1, interests=["chess", "hiking"])

    topic, is_genuine = shared_interest(persona, {"hiking": 1.0, "chess": 5.0})

    assert topic == "chess"
    assert is_genuine is True


def test__shared_interest_falls_back_when_no_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "sensitive_topics", lambda: frozenset())
    persona = _persona(1, interests=["pottery"])

    topic, is_genuine = shared_interest(persona, {"hiking": 1.0, "chess": 2.0})

    assert topic == "chess"
    assert is_genuine is False


def test__shared_interest_excludes_sensitive_topics_even_when_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "sensitive_topics", lambda: frozenset({"progressive activism"}))
    persona = _persona(1, interests=["progressive activism", "hiking"])

    topic, is_genuine = shared_interest(persona, {"progressive activism": 10.0, "hiking": 1.0})

    assert topic == "hiking"
    assert is_genuine is True


def test__shared_interest_raises_when_all_user_interests_are_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "sensitive_topics", lambda: frozenset({"conservative politics"}))
    persona = _persona(1, interests=["hiking"])

    with pytest.raises(ValueError):
        shared_interest(persona, {"conservative politics": 1.0})


def test__is_free_now_true_when_current_hour_is_in_free_hours() -> None:
    current_hour = datetime.now(UTC).hour
    persona = _persona(1, free_hours=[current_hour])

    assert is_free_now(persona) is True


def test__is_free_now_false_when_current_hour_is_not_in_free_hours() -> None:
    current_hour = datetime.now(UTC).hour
    other_hour = (current_hour + 12) % 24

    assert is_free_now(_persona(1, free_hours=[other_hour])) is False


def test__select_proactive_persona_none_with_no_engagement_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "get_persona_engagement_token_counts", lambda user_id: {})

    assert select_proactive_persona(_user()) is None


def test__select_proactive_persona_none_when_nobody_in_top_four_is_free(monkeypatch: pytest.MonkeyPatch) -> None:
    busy = _persona(1, free_hours=[])
    monkeypatch.setattr(selection_module, "get_persona_engagement_token_counts", lambda user_id: {1: 10})
    monkeypatch.setattr(selection_module, "get_persona", lambda persona_id: busy)

    assert select_proactive_persona(_user()) is None


def test__select_proactive_persona_picks_among_the_free_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    free_persona = _persona(2, free_hours=list(range(24)))
    busy_persona = _persona(1, free_hours=[])
    personas = {1: busy_persona, 2: free_persona}
    monkeypatch.setattr(selection_module, "get_persona_engagement_token_counts", lambda user_id: {1: 100, 2: 50})
    monkeypatch.setattr(selection_module, "get_persona", lambda persona_id: personas[persona_id])

    assert select_proactive_persona(_user()) == free_persona


def test__select_proactive_persona_only_considers_the_top_four_by_engagement(monkeypatch: pytest.MonkeyPatch) -> None:
    # Five candidates; only the 5th (lowest engagement) is free. It should never be picked -
    # only the top 4 by token count are eligible at all.
    personas = {i: _persona(i, free_hours=list(range(24)) if i == 5 else []) for i in range(1, 6)}
    counts = {1: 50, 2: 40, 3: 30, 4: 20, 5: 10}
    monkeypatch.setattr(selection_module, "get_persona_engagement_token_counts", lambda user_id: counts)
    monkeypatch.setattr(selection_module, "get_persona", lambda persona_id: personas[persona_id])

    assert select_proactive_persona(_user()) is None
