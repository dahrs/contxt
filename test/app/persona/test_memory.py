from __future__ import annotations

import pytest

import app.persona.memory as memory_module
from app.db.models import Message, MessageRole, Persona, PersonaMemory, User
from app.persona.memory import sync_relationship_memory
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
        is_beginner_teacher=False,
        interests=[],
    )


def _message(id_: int, role: MessageRole, text: str) -> Message:
    return Message(id=id_, conversation_id=1, role=role, text=text, created_at="x")


def test__sync_relationship_memory_is_a_noop_when_nothing_new(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(
        user_id=1, persona_id=1, summary="old summary", last_summarized_message_id=5, updated_at="x"
    )
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [])
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: pytest.fail("should not upsert"))

    summary = sync_relationship_memory(fake_llm, _user(), _persona())

    assert summary == "old summary"
    assert fake_llm.judge_calls == []


def test__sync_relationship_memory_folds_new_messages_and_advances_watermark(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    existing = PersonaMemory(user_id=1, persona_id=1, summary="", last_summarized_message_id=None, updated_at="x")
    new_messages = [_message(7, "user", "I'm a software engineer"), _message(8, "assistant", "neat!")]
    upserted_calls: list[tuple[int, int, str, int]] = []
    fake_llm.judge_response = "updated summary text"

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

    summary = sync_relationship_memory(fake_llm, _user(), _persona())

    assert summary == "updated summary text"
    assert upserted_calls == [(1, 1, "updated summary text", 8)]
    assert len(fake_llm.judge_calls) == 1
    _, user_prompt, _ = fake_llm.judge_calls[0]
    assert "software engineer" in user_prompt


def test__summarization_prompt_sets_an_explicit_length_cap(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> None:
    """Regression guard: without an explicit cap, the summary can only grow across many
    conversations with the same persona (each fold-in sees the old summary plus new material)."""
    existing = PersonaMemory(user_id=1, persona_id=1, summary="prior", last_summarized_message_id=0, updated_at="x")
    monkeypatch.setattr(memory_module, "get_memory", lambda user_id, persona_id: existing)
    monkeypatch.setattr(
        memory_module, "get_messages_with_persona_after", lambda user_id, persona_id, after: [_message(1, "user", "hi")]
    )
    monkeypatch.setattr(memory_module, "upsert_memory", lambda *a, **kw: None)

    sync_relationship_memory(fake_llm, _user(), _persona())

    system_prompt, _, _ = fake_llm.judge_calls[0]
    assert "words" in system_prompt
