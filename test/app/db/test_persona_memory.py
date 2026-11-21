from __future__ import annotations

from app.db.persona_memory import get_memory, upsert_memory
from app.db.users import create_user
from test.factories import make_persona


def _ids() -> tuple[int, int, int]:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    persona_a = make_persona(name="A")
    persona_b = make_persona(name="B")
    return user.id, persona_a.id, persona_b.id


def test__get_memory_defaults_to_empty_for_unmet_pair() -> None:
    user_id, persona_id, _ = _ids()

    memory = get_memory(user_id, persona_id)

    assert memory.summary == ""
    assert memory.last_summarized_message_id is None


def test__upsert_memory_then_get_memory_roundtrip() -> None:
    user_id, persona_id, _ = _ids()

    upsert_memory(user_id, persona_id, summary="likes hiking", last_summarized_message_id=5)
    memory = get_memory(user_id, persona_id)

    assert memory.summary == "likes hiking"
    assert memory.last_summarized_message_id == 5


def test__upsert_memory_overwrites_previous_summary_for_same_pair() -> None:
    user_id, persona_id, _ = _ids()

    upsert_memory(user_id, persona_id, summary="first", last_summarized_message_id=1)
    upsert_memory(user_id, persona_id, summary="second", last_summarized_message_id=2)

    assert get_memory(user_id, persona_id).summary == "second"


def test__memory_is_isolated_per_persona() -> None:
    user_id, persona_a_id, persona_b_id = _ids()

    upsert_memory(user_id, persona_a_id, summary="told persona A this", last_summarized_message_id=1)

    assert get_memory(user_id, persona_b_id).summary == ""
