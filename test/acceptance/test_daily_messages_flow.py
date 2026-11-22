from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.auth.security import hash_password
from app.db.conversations import add_message, create_conversation, list_conversations
from app.db.users import create_user, get_user_by_id, set_interests, set_last_proactive_sent_at
from scripts.send_daily_messages import main
from test.conftest import FakeLLMClient
from test.factories import make_persona


def test__daily_messages_sends_a_proactive_conversation_to_an_engaged_user(
    use_fake_llm: FakeLLMClient, capsys: pytest.CaptureFixture[str]
) -> None:
    current_hour = datetime.now(UTC).hour
    persona = make_persona(free_hours=[current_hour])
    user = create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(user.id, {"travel": 1.0})
    # Existing engagement history, with a real user-sent message so the ranking has something to go on.
    conversation = create_conversation(user.id, persona.id, "travel", [])
    add_message(conversation.id, "user", "hello there, nice to meet you")

    use_fake_llm.generate_response = ("hey, thought of you today!", "cli-session-proactive")

    exit_code = main()

    assert exit_code == 0
    assert "Sent 1 proactive message" in capsys.readouterr().out
    conversations = list_conversations(user.id)
    proactive = [c for c in conversations if c.is_proactive]
    assert len(proactive) == 1
    assert proactive[0].persona_id == persona.id
    assert get_user_by_id(user.id).last_proactive_sent_at is not None  # type: ignore[union-attr]


def test__daily_messages_skips_users_with_no_conversation_history(use_fake_llm: FakeLLMClient) -> None:
    make_persona(free_hours=list(range(24)))
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(1, {"travel": 1.0})

    exit_code = main()

    assert exit_code == 0
    assert list_conversations(1) == []


def test__daily_messages_respects_the_cooldown(use_fake_llm: FakeLLMClient) -> None:
    current_hour = datetime.now(UTC).hour
    persona = make_persona(free_hours=[current_hour])
    user = create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(user.id, {"travel": 1.0})
    conversation = create_conversation(user.id, persona.id, "travel", [])
    add_message(conversation.id, "user", "hello there")
    recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    set_last_proactive_sent_at(user.id, recent)

    use_fake_llm.generate_response = ("hey!", "cli-session-proactive")
    main()

    proactive = [c for c in list_conversations(user.id) if c.is_proactive]
    assert proactive == []


def test__daily_messages_never_selects_the_beginner_teacher(use_fake_llm: FakeLLMClient) -> None:
    current_hour = datetime.now(UTC).hour
    teacher = make_persona(is_beginner_teacher=True, free_hours=[current_hour])
    user = create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(user.id, {"travel": 1.0})
    conversation = create_conversation(user.id, teacher.id, "help", [])
    add_message(conversation.id, "user", "can you explain this word")

    use_fake_llm.generate_response = ("hey!", "cli-session-proactive")
    main()

    assert [c for c in list_conversations(user.id) if c.is_proactive] == []
