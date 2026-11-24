from __future__ import annotations

from app.db.conversations import (
    add_item_event,
    add_message,
    create_conversation,
    get_conversation,
    get_judged_item_ids,
    get_messages,
    get_messages_with_persona_after,
    get_most_recent_conversation_with_persona,
    get_most_recent_persona_id,
    get_persona_engagement_token_counts,
    get_recent_topics,
    list_conversations,
)
from app.db.milestones import create_milestone
from app.db.skills import create_skill_item
from app.db.users import create_user
from test.factories import make_persona as _make_persona


def _milestone_id() -> int:
    return create_milestone("Greetings", "Can greet someone", "A1").id


def test__create_conversation_roundtrip() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    persona = _make_persona()
    item = create_skill_item("vocab", "eng", "fra", "bonjour", _milestone_id())

    conversation = create_conversation(user.id, persona.id, "travel", [item.id])

    assert conversation.user_id == user.id
    assert conversation.persona_id == persona.id
    assert conversation.target_item_ids == [item.id]
    assert get_conversation(conversation.id) == conversation


def test__get_conversation_missing_returns_none() -> None:
    assert get_conversation(999) is None


def test__add_message_and_get_messages_in_order() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    conversation = create_conversation(user.id, _make_persona().id, "travel", [])

    add_message(conversation.id, "assistant", "bonjour!")
    add_message(conversation.id, "user", "salut")

    texts = [m.text for m in get_messages(conversation.id)]
    assert texts == ["bonjour!", "salut"]


def test__get_judged_item_ids_reflects_recorded_events() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    item = create_skill_item("vocab", "eng", "fra", "bonjour", _milestone_id())
    conversation = create_conversation(user.id, _make_persona().id, "travel", [item.id])
    message = add_message(conversation.id, "user", "bonjour")

    assert get_judged_item_ids(conversation.id) == set()

    add_item_event(message.id, item.id, "correct")

    assert get_judged_item_ids(conversation.id) == {item.id}


def test__get_most_recent_persona_id_picks_latest_conversation() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    first = _make_persona()
    second = _make_persona()
    create_conversation(user.id, first.id, "travel", [])
    create_conversation(user.id, second.id, "cooking", [])

    assert get_most_recent_persona_id(user.id) == second.id


def test__get_most_recent_persona_id_none_when_no_conversations() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")

    assert get_most_recent_persona_id(user.id) is None


def test__get_messages_with_persona_after_only_returns_newer_messages_with_that_persona() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    persona_a = _make_persona()
    persona_b = _make_persona()
    conv_a = create_conversation(user.id, persona_a.id, "travel", [])
    conv_b = create_conversation(user.id, persona_b.id, "cooking", [])
    add_message(conv_a.id, "user", "to persona a")
    second = add_message(conv_a.id, "assistant", "reply from a")
    add_message(conv_b.id, "user", "to persona b")

    newer = get_messages_with_persona_after(user.id, persona_a.id, after_message_id=0)
    assert [m.text for m in newer] == ["to persona a", "reply from a"]

    only_after_first = get_messages_with_persona_after(user.id, persona_a.id, after_message_id=second.id - 1)
    assert [m.id for m in only_after_first] == [second.id]


def test__list_conversations_orders_newest_first() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    create_conversation(user.id, _make_persona().id, "first", [])
    create_conversation(user.id, _make_persona().id, "second", [])

    topics = [c.topic for c in list_conversations(user.id)]
    assert topics == ["second", "first"]


def test__get_recent_topics_respects_limit() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    for topic in ("a", "b", "c"):
        create_conversation(user.id, _make_persona().id, topic, [])

    assert get_recent_topics(user.id, limit=2) == ["c", "b"]


def test__get_persona_engagement_token_counts_counts_user_messages_only() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    persona = _make_persona()
    conversation = create_conversation(user.id, persona.id, "travel", [])
    add_message(conversation.id, "user", "one two three")
    add_message(conversation.id, "assistant", "this is a much longer reply with many more words")
    add_message(conversation.id, "user", "four five")

    counts = get_persona_engagement_token_counts(user.id)

    assert counts == {persona.id: 5}  # 3 + 2 user-sent tokens, the assistant's words never count


def test__get_persona_engagement_token_counts_excludes_beginner_teacher() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    teacher = _make_persona(is_beginner_teacher=True)
    conversation = create_conversation(user.id, teacher.id, "help", [])
    add_message(conversation.id, "user", "lots and lots of words here to the teacher")

    assert get_persona_engagement_token_counts(user.id) == {}


def test__get_persona_engagement_token_counts_sums_across_multiple_conversations() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    persona = _make_persona()
    first = create_conversation(user.id, persona.id, "travel", [])
    second = create_conversation(user.id, persona.id, "cooking", [])
    add_message(first.id, "user", "one two")
    add_message(second.id, "user", "three four five")

    assert get_persona_engagement_token_counts(user.id) == {persona.id: 5}


def test__get_most_recent_conversation_with_persona_found_and_missing() -> None:
    user = create_user("alice", "pw", "Alice", "eng", "fra")
    persona_a = _make_persona()
    persona_b = _make_persona()
    create_conversation(user.id, persona_a.id, "first", [])
    latest = create_conversation(user.id, persona_a.id, "second", [])

    assert get_most_recent_conversation_with_persona(user.id, persona_a.id) == latest
    assert get_most_recent_conversation_with_persona(user.id, persona_b.id) is None
