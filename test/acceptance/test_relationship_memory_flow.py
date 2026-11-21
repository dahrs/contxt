from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.persona_memory import upsert_memory
from app.db.personas import get_persona
from app.db.users import create_user, set_interests
from test.conftest import FakeLLMClient
from test.factories import make_persona


def _sync_response(summary: str, **character_updates: object) -> str:
    defaults: dict[str, object] = {
        "interests_added": [],
        "interests_removed": [],
        "daily_routine": None,
        "background": None,
    }
    defaults.update(character_updates)
    return json.dumps({"relationship_summary": summary, "character_updates": defaults})


def test__second_conversation_with_same_persona_carries_relationship_memory_forward(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    # Exactly one regular persona: select_persona's "avoid most-recent" fallback (`or roster`)
    # guarantees the same persona is picked again on conversation #2, deterministically.
    make_persona()
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(1, {"travel": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})

    use_fake_llm.generate_response = ("hi there", "cli-session-1")
    first = client.post("/chat/new", follow_redirects=False)
    first_conversation_id = int(first.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/chat/{first_conversation_id}/message", data={"text": "I'm a nurse who loves hiking"})

    use_fake_llm.judge_response = _sync_response("Alice is a nurse who loves hiking - warm, hardworking person.")
    use_fake_llm.generate_response = ("hi again", "cli-session-2")
    client.post("/chat/new", follow_redirects=False)

    second_system_prompt = use_fake_llm.generate_calls[-1][0]
    first_system_prompt = use_fake_llm.generate_calls[0][0]
    assert "nurse who loves hiking" in second_system_prompt
    assert "nurse who loves hiking" not in first_system_prompt


def test__character_sheet_update_persists_into_the_next_conversation(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    """The actual scenario this exists for: the persona commits in-character to a hobby change,
    and the *next* conversation's prompt reflects the updated character sheet - not frozen
    conversation history, an actual change to who this persona is going forward."""
    persona = make_persona(interests=["cooking"])
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    # Alice is into painting, not cooking - no overlap yet, so shared_interest() won't surface
    # the persona's interests in the prompt until after the update below creates one.
    set_interests(1, {"painting": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})

    use_fake_llm.generate_response = ("hi there", "cli-session-1")
    first = client.post("/chat/new", follow_redirects=False)
    first_conversation_id = int(first.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/chat/{first_conversation_id}/message", data={"text": "Do you still cook much?"})

    use_fake_llm.judge_response = _sync_response(
        "They asked about cooking.", interests_added=["painting"], interests_removed=["cooking"]
    )
    use_fake_llm.generate_response = ("hi again", "cli-session-2")
    client.post("/chat/new", follow_redirects=False)

    updated = get_persona(persona.id)
    assert updated is not None
    assert "painting" in updated.interests
    assert "cooking" not in updated.interests

    # Before the update there's no real overlap (persona likes cooking, Alice likes painting) -
    # shared_interest() falls back to framing Alice's own interest as something new to the
    # persona. After the update, persona and Alice genuinely share "painting" - the framing
    # should flip from fallback to genuine, proving the new conversation actually reads the
    # updated character sheet rather than the one frozen at the start of conversation #1.
    first_system_prompt = use_fake_llm.generate_calls[0][0]
    second_system_prompt = use_fake_llm.generate_calls[-1][0]
    assert "recently found yourself curious about painting" in first_system_prompt
    assert "both happen to be into painting" in second_system_prompt


def test__a_different_persona_never_sees_another_persona_s_relationship_memory(
    client: TestClient, use_fake_llm: FakeLLMClient
) -> None:
    persona_a = make_persona(name="Persona A")
    make_persona(name="Persona B")
    create_user("alice", hash_password("testpass"), "Alice", "eng", "fra")
    set_interests(1, {"travel": 1.0})
    client.post("/login", data={"username": "alice", "password": "testpass"})

    # Pre-seed persona A's memory before any conversation happens, so which persona the random
    # pick lands on (either is possible with two in the roster) still gives a deterministic
    # assertion either way: persona A's own prompt should carry it, persona B's never should.
    upsert_memory(1, persona_a.id, summary="told persona A she is a nurse", last_summarized_message_id=0)

    use_fake_llm.generate_response = ("hi", "cli-session-1")
    client.post("/chat/new", follow_redirects=False)

    system_prompt = use_fake_llm.generate_calls[0][0]
    if "Persona A" in system_prompt:
        assert "told persona A she is a nurse" in system_prompt
    else:
        assert "Persona B" in system_prompt
        assert "told persona A she is a nurse" not in system_prompt
