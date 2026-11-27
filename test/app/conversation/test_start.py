from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import app.conversation.start as start_module
from app.conversation.session_plan import LearnerProfileSummary, SessionPlan
from app.conversation.start import elapsed_since, start_conversation
from app.db.models import Conversation, Persona, User
from test.conftest import FakeLLMClient


def test__elapsed_since_none_for_none_timestamp() -> None:
    assert elapsed_since(None) is None


def test__elapsed_since_computes_a_positive_delta_for_a_past_timestamp() -> None:
    past = (datetime.now(UTC) - timedelta(hours=3)).isoformat()

    delta = elapsed_since(past)

    assert delta is not None
    assert delta.total_seconds() > 3600 * 2.9


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


def _persona(id_: int = 1) -> Persona:
    return Persona(
        id=id_,
        target_lang="fra",
        name="Camille",
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
        free_hours=list(range(24)),
        is_beginner_teacher=False,
        interests=[],
    )


def _plan(user: User) -> SessionPlan:
    return SessionPlan(
        user=user,
        topic="travel",
        due_items=[],
        new_items=[],
        current_milestone=None,
        learner_profile=LearnerProfileSummary(known_item_count=0, known_milestones={}, chronic_issue_items=[]),
        engagement_topics=[],
    )


def test__start_conversation_creates_conversation_and_stores_opening_message(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    user = _user()
    persona = _persona()
    created_conversations: list[tuple[int, int, bool]] = []
    stored_messages: list[tuple[int, str, str]] = []
    fake_llm.generate_response = ("hi there", "cli-session-1")

    monkeypatch.setattr(start_module, "sync_after_conversation", lambda llm, u, p: "")
    monkeypatch.setattr(start_module, "get_persona", lambda persona_id: persona)
    monkeypatch.setattr(start_module, "list_conversations", lambda user_id: [])
    monkeypatch.setattr(start_module, "build_session_plan", lambda u: _plan(u))
    monkeypatch.setattr(start_module, "shared_interest", lambda p, interests: ("travel", False))
    monkeypatch.setattr(start_module, "get_interests", lambda user_id: {"travel": 1.0})

    def fake_create_conversation(
        user_id: int, persona_id: int, topic: str, target_item_ids: list[int], is_proactive: bool = False
    ) -> Conversation:
        created_conversations.append((user_id, persona_id, is_proactive))
        return Conversation(
            id=42,
            user_id=user_id,
            persona_id=persona_id,
            topic=topic,
            claude_session_id=None,
            target_item_ids=target_item_ids,
            is_proactive=is_proactive,
            started_at="x",
        )

    monkeypatch.setattr(start_module, "create_conversation", fake_create_conversation)
    monkeypatch.setattr(start_module, "set_claude_session_id", lambda conversation_id, session_id: None)
    monkeypatch.setattr(
        start_module,
        "add_message",
        lambda conversation_id, role, text: stored_messages.append((conversation_id, role, text)),
    )

    conversation = start_conversation(fake_llm, user, persona, "(kickoff)", is_proactive=True)

    assert conversation.id == 42
    assert created_conversations == [(user.id, persona.id, True)]
    assert stored_messages == [(42, "assistant", "hi there")]
    assert fake_llm.generate_calls[0][2] == "(kickoff)"
