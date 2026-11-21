from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.conversations import get_conversation
from app.db.users import create_user, set_interests
from test.conftest import FakeLLMClient
from test.factories import make_persona


def test__absolute_beginners_first_conversation_gets_the_beginner_teacher_persona(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    beginner_teacher = make_persona(is_beginner_teacher=True)
    make_persona(name="Regular Persona")
    create_user("bob", hash_password("testpass"), "Bob", "eng", "fra", is_absolute_beginner=True)
    set_interests(1, {"software engineering": 1.0})
    client.post("/login", data={"username": "bob", "password": "testpass"})

    response = client.post("/chat/new", follow_redirects=False)
    conversation_id = int(response.headers["location"].rsplit("/", 1)[-1])

    assert get_conversation(conversation_id).persona_id == beginner_teacher.id  # type: ignore[union-attr]


def test__normal_users_first_conversation_never_gets_the_beginner_teacher_persona(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    make_persona(is_beginner_teacher=True)
    regular = make_persona(name="Regular Persona")
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra", is_absolute_beginner=False)
    set_interests(1, {"software engineering": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})

    response = client.post("/chat/new", follow_redirects=False)
    conversation_id = int(response.headers["location"].rsplit("/", 1)[-1])

    assert get_conversation(conversation_id).persona_id == regular.id  # type: ignore[union-attr]
