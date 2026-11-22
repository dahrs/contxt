from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.conversations import create_conversation
from app.db.users import create_user, set_interests
from test.factories import make_persona


def test__chat_index_shows_available_and_busy_personas_the_user_has_talked_to(client: TestClient) -> None:
    current_hour = datetime.now(UTC).hour
    other_hour = (current_hour + 12) % 24
    free_persona = make_persona(name="Free Persona", free_hours=[current_hour])
    busy_persona = make_persona(name="Busy Persona", free_hours=[other_hour])
    user = create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(user.id, {"travel": 1.0})
    create_conversation(user.id, free_persona.id, "travel", [])
    create_conversation(user.id, busy_persona.id, "cooking", [])
    client.post("/login", data={"username": "alice", "password": "testpass"})

    page = client.get("/chat")

    assert "Free Persona" in page.text
    assert "Busy Persona" in page.text
    # Specifically in the right bucket, not just present anywhere on the page.
    available_section = page.text.split("Available now:")[1].split("Probably busy:")[0]
    assert "Free Persona" in available_section
    assert "Busy Persona" not in available_section


def test__chat_index_omits_availability_line_for_a_brand_new_user_with_no_history(client: TestClient) -> None:
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(1, {"travel": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})

    page = client.get("/chat")

    assert "Available now" not in page.text
    assert "Probably busy" not in page.text
