from __future__ import annotations

import json

import pytest

import app.persona.memory as memory_module
from app.db.models import Message, MessageRole, Persona, PersonaMemory, User
from app.persona.memory import sync_after_conversation
from test.conftest import FakeLLMClient


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


def _persona() -> Persona:
    return Persona(
        id=1,
        target_lang="fra",
        name="Camille",
        origin="Tours",
        age=34,
        background="N/A",
        physical_description="N/A",
        psychological_profile="warm and curious",
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
        interests=["cooking"],
    )


def _message(id_: int, role: MessageRole, text: str) -> Message:
    return Message(id=id_, conversation_id=1, role=role, text=text, created_at="x")


def _sync_response(
    summary: str = "updated summary text",
    engagement_topics: list[dict[str, object]] | None = None,
    **character_updates: object,
) -> str:
    defaults: dict[str, object] = {
        "interests_added": [],
        "interests_removed": [],
        "daily_routine": None,
        "background": None,
    }
    defaults.update(character_updates)
    return json.dumps(
        {
            "relationship_summary": summary,
            "character_updates": defaults,
            "engagement_topics": engagement_topics or [],
        }
    )


def test__sync_after_conversation_is_a_noop_when_nothing_new(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(
        user_id=1, persona_id=1, summary="old summary", last_summarized_message_id=5, updated_at="x"
    )
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [])
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: pytest.fail("should not upsert"))

    summary = sync_after_conversation(fake_llm, _user(), _persona())

    assert summary == "old summary"
    assert fake_llm.judge_calls == []


def test__sync_after_conversation_folds_new_messages_and_advances_watermark(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=None, updated_at="x")
    new_messages = [_message(7, "user", "I'm a software engineer"), _message(8, "assistant", "neat!")]
    upserted_calls: list[tuple[int, int, str, int]] = []
    fake_llm.judge_response = _sync_response()

    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: new_messages
    )
    monkeypatch.setattr(
        memory_module,
        "upsert_memory",
        lambda user_id, persona_id, summary, last_summarized_message_id: upserted_calls.append(
            (user_id, persona_id, summary, last_summarized_message_id)
        ),
    )

    summary = sync_after_conversation(fake_llm, _user(), _persona())

    assert summary == "updated summary text"
    assert upserted_calls == [(1, 1, "updated summary text", 8)]
    assert len(fake_llm.judge_calls) == 1
    _, user_prompt, _ = fake_llm.judge_calls[0]
    assert "software engineer" in user_prompt


def test__sync_prompt_sets_an_explicit_length_cap(monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient) -> None:
    """Regression guard: without an explicit cap, the summary can only grow across many
    conversations with the same persona (each fold-in sees the old summary plus new material)."""
    existing = PersonaMemory(user_id=1, persona_id=1, summary="prior", last_summarized_message_id=0, updated_at="x")
    fake_llm.judge_response = _sync_response()
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)

    sync_after_conversation(fake_llm, _user(), _persona())

    system_prompt, _, _ = fake_llm.judge_calls[0]
    assert "words" in system_prompt


def test__sync_after_conversation_falls_back_to_prior_summary_on_unparseable_output(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(
        user_id=1, persona_id=1, summary="prior summary", last_summarized_message_id=0, updated_at="x"
    )
    fake_llm.judge_response = "not json at all"
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: pytest.fail("should not upsert"))

    summary = sync_after_conversation(fake_llm, _user(), _persona())

    assert summary == "prior summary"


def test__sync_after_conversation_applies_interest_changes(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=0, updated_at="x")
    fake_llm.judge_response = _sync_response(interests_added=["painting"], interests_removed=["cooking"])
    added: list[tuple[int, str]] = []
    removed: list[tuple[int, str]] = []
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)
    monkeypatch.setattr(
        memory_module, "add_persona_interest", lambda persona_id, topic: added.append((persona_id, topic))
    )
    monkeypatch.setattr(
        memory_module, "remove_persona_interest", lambda persona_id, topic: removed.append((persona_id, topic))
    )

    sync_after_conversation(fake_llm, _user(), _persona())

    assert added == [(1, "painting")]
    assert removed == [(1, "cooking")]


def test__sync_after_conversation_applies_daily_routine_change(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=0, updated_at="x")
    fake_llm.judge_response = _sync_response(daily_routine="now an early riser, up at 6am")
    updates: list[tuple[int, str | None, str | None]] = []
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)
    monkeypatch.setattr(
        memory_module,
        "update_persona_character",
        lambda persona_id, daily_routine=None, background=None: updates.append((persona_id, daily_routine, background)),
    )

    sync_after_conversation(fake_llm, _user(), _persona())

    assert updates == [(1, "now an early riser, up at 6am", None)]


def test__sync_after_conversation_records_engagement_topics(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=0, updated_at="x")
    fake_llm.judge_response = _sync_response(
        engagement_topics=[
            {"topic": "half-marathon training", "valence": "positive", "follow_up_note": "ask how the race went"},
            {"topic": "job stress", "valence": "negative", "follow_up_note": "ask how work has been lately"},
        ]
    )
    recorded: list[tuple[int, str, str, str]] = []
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)
    monkeypatch.setattr(memory_module, "get_interests", lambda user_id: {})
    monkeypatch.setattr(memory_module, "set_interests", lambda *a, **kw: None)
    monkeypatch.setattr(
        memory_module,
        "add_engagement_topic",
        lambda user_id, topic, valence, note: recorded.append((user_id, topic, valence, note)),
    )

    sync_after_conversation(fake_llm, _user(), _persona())

    assert recorded == [
        (1, "half-marathon training", "positive", "ask how the race went"),
        (1, "job stress", "negative", "ask how work has been lately"),
    ]


def test__sync_after_conversation_bumps_interest_weight_for_positive_engagement_topic_only(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=0, updated_at="x")
    fake_llm.judge_response = _sync_response(
        engagement_topics=[
            {"topic": "running", "valence": "positive", "follow_up_note": "note"},
            {"topic": "job stress", "valence": "negative", "follow_up_note": "note"},
        ]
    )
    set_interests_calls: list[dict[str, float]] = []
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)
    monkeypatch.setattr(memory_module, "add_engagement_topic", lambda *a, **kw: None)
    monkeypatch.setattr(memory_module, "get_interests", lambda user_id: {"running": 1.0})
    monkeypatch.setattr(memory_module, "set_interests", lambda user_id, topics: set_interests_calls.append(topics))

    sync_after_conversation(fake_llm, _user(), _persona())

    assert len(set_interests_calls) == 1
    assert set_interests_calls[0]["running"] == 1.5
    assert "job stress" not in set_interests_calls[0]


def test__sync_after_conversation_does_not_touch_interests_when_no_positive_engagement_topics(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=0, updated_at="x")
    fake_llm.judge_response = _sync_response(
        engagement_topics=[{"topic": "job stress", "valence": "negative", "follow_up_note": "note"}]
    )
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)
    monkeypatch.setattr(memory_module, "add_engagement_topic", lambda *a, **kw: None)
    monkeypatch.setattr(memory_module, "get_interests", lambda user_id: pytest.fail("should not be read"))
    monkeypatch.setattr(memory_module, "set_interests", lambda *a, **kw: pytest.fail("should not set"))

    sync_after_conversation(fake_llm, _user(), _persona())


def test__sync_after_conversation_does_not_touch_character_sheet_when_no_commitments(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=0, updated_at="x")
    fake_llm.judge_response = _sync_response()
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)
    monkeypatch.setattr(memory_module, "update_persona_character", lambda *a, **kw: pytest.fail("should not update"))
    monkeypatch.setattr(memory_module, "add_persona_interest", lambda *a, **kw: pytest.fail("should not add"))

    sync_after_conversation(fake_llm, _user(), _persona())
