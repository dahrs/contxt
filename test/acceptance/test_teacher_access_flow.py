from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.conversations import get_conversation
from app.db.users import create_user, set_interests
from test.conftest import FakeLLMClient
from test.factories import make_persona


def test__chat_teacher_continues_existing_thread_instead_of_starting_a_new_one(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    teacher = make_persona(is_beginner_teacher=True)
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(1, {"travel": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})

    use_fake_llm.generate_response = ("bonjour!", "cli-session-1")
    first = client.post("/chat/teacher", follow_redirects=False)
    first_conversation_id = first.headers["location"].rsplit("/", 1)[-1]

    second = client.post("/chat/teacher", follow_redirects=False)
    second_conversation_id = second.headers["location"].rsplit("/", 1)[-1]

    assert first_conversation_id == second_conversation_id
    assert len(use_fake_llm.generate_calls) == 1  # the second call never generated a new opener
    assert get_conversation(int(first_conversation_id)).persona_id == teacher.id  # type: ignore[union-attr]


def test__chat_teacher_redirects_home_when_no_teacher_exists_for_the_language(client: TestClient) -> None:
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(1, {"travel": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})

    response = client.post("/chat/teacher", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/chat"
