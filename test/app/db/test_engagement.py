from __future__ import annotations

from app.db.engagement import add_engagement_topic, get_unsurfaced_engagement_topics, mark_engagement_topics_surfaced
from app.db.users import create_user


def _user_id() -> int:
    return create_user("alice", "pw", "Alice", "eng", "fra").id


def test__get_unsurfaced_engagement_topics_empty_when_none_recorded() -> None:
    assert get_unsurfaced_engagement_topics(_user_id(), limit=5) == []


def test__add_engagement_topic_then_get_unsurfaced_roundtrip() -> None:
    user_id = _user_id()

    add_engagement_topic(user_id, "half-marathon training", "positive", "ask how the race went")
    topics = get_unsurfaced_engagement_topics(user_id, limit=5)

    assert len(topics) == 1
    assert topics[0].topic == "half-marathon training"
    assert topics[0].valence == "positive"
    assert topics[0].follow_up_note == "ask how the race went"
    assert topics[0].surfaced_at is None


def test__get_unsurfaced_engagement_topics_respects_limit() -> None:
    user_id = _user_id()
    for i in range(5):
        add_engagement_topic(user_id, f"topic-{i}", "positive", "note")

    topics = get_unsurfaced_engagement_topics(user_id, limit=2)

    assert len(topics) == 2


def test__mark_engagement_topics_surfaced_excludes_them_from_later_fetches() -> None:
    user_id = _user_id()
    add_engagement_topic(user_id, "topic-a", "positive", "note")
    add_engagement_topic(user_id, "topic-b", "negative", "note")
    topics = get_unsurfaced_engagement_topics(user_id, limit=5)
    assert len(topics) == 2

    mark_engagement_topics_surfaced([topics[0].id])

    remaining = get_unsurfaced_engagement_topics(user_id, limit=5)
    assert len(remaining) == 1
    assert remaining[0].id == topics[1].id


def test__mark_engagement_topics_surfaced_is_a_noop_for_empty_list() -> None:
    user_id = _user_id()
    add_engagement_topic(user_id, "topic-a", "positive", "note")

    mark_engagement_topics_surfaced([])

    assert len(get_unsurfaced_engagement_topics(user_id, limit=5)) == 1


def test__engagement_topics_are_isolated_per_user() -> None:
    user_a = _user_id()
    user_b = create_user("bob", "pw", "Bob", "eng", "fra").id

    add_engagement_topic(user_a, "topic-a", "positive", "note")

    assert get_unsurfaced_engagement_topics(user_b, limit=5) == []
