from __future__ import annotations

import pytest

import app.persona.selection as selection_module
from app.db.models import Conversation, Persona, User
from app.persona.selection import is_first_conversation, select_persona, shared_interest


def _user(is_absolute_beginner: bool = False) -> User:
    return User(
        id=1,
        username="alice",
        password_hash="x",
        display_name="Alice",
        native_lang="eng",
        target_lang="fra",
        is_absolute_beginner=is_absolute_beginner,
        created_at="2026-01-01T00:00:00Z",
    )


def _persona(id_: int, interests: list[str] | None = None) -> Persona:
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
        is_beginner_teacher=False,
        interests=interests or [],
    )


def _conversation() -> Conversation:
    return Conversation(
        id=1, user_id=1, persona_id=1, topic="travel", claude_session_id=None, target_item_ids=[], started_at="x"
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
