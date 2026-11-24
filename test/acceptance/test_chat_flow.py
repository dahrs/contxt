from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.conversations import get_judged_item_ids
from app.db.memory import get_state
from app.db.milestones import create_milestone
from app.db.skills import create_skill_item
from app.db.users import create_user, set_interests
from test.conftest import FakeLLMClient
from test.factories import make_persona


def _login(client: TestClient) -> None:
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(1, {"travel": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})


def test__starting_a_new_conversation_creates_persona_linked_conversation_with_opening_message(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    make_persona()
    use_fake_llm.generate_response = ("Salut! Comment vas-tu?", "cli-session-1")
    _login(client)

    response = client.post("/chat/new", follow_redirects=False)
    assert response.status_code == 303
    conversation_id = response.headers["location"].rsplit("/", 1)[-1]

    page = client.get(f"/chat/{conversation_id}")
    assert "Salut! Comment vas-tu?" in page.text
    assert len(use_fake_llm.generate_calls) == 1
    system_prompt, session_id, _ = use_fake_llm.generate_calls[0]
    assert session_id is None  # first turn - no session to resume yet
    assert "excuse yourself" in system_prompt  # the shared guardrails fragment made it in


def test__sending_a_message_runs_signal_extraction_and_updates_memory(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    make_persona()
    milestone = create_milestone("Greetings", "Can greet someone", "A1")
    item = create_skill_item("vocab", "eng", "fra", "bonjour", milestone.id)
    use_fake_llm.generate_response = ("opening message", "cli-session-1")
    _login(client)
    new_conv = client.post("/chat/new", follow_redirects=False)
    conversation_id = int(new_conv.headers["location"].rsplit("/", 1)[-1])

    # the session plan picked whatever frontier item existed when the conversation started -
    # force the judge to report that item as correctly used.
    use_fake_llm.judge_response = f'{{"outcomes": [{{"item_id": {item.id}, "outcome": "correct"}}]}}'
    use_fake_llm.generate_response = ("great job!", "cli-session-1")

    response = client.post(f"/chat/{conversation_id}/message", data={"text": "Bonjour!"}, follow_redirects=False)
    assert response.status_code == 303

    assert get_judged_item_ids(conversation_id) == {item.id}
    state = get_state(1, item.id)
    assert state is not None
    assert state.reps == 1
