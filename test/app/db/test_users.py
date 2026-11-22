from __future__ import annotations

from app.db.users import (
    create_user,
    get_interests,
    get_user_by_id,
    get_user_by_username,
    list_all_users,
    set_interests,
    set_last_proactive_sent_at,
)


def test__create_user_roundtrip() -> None:
    user = create_user("alice", "hashed-pw", "Alice", "eng", "fra")

    assert user.id is not None
    assert user.username == "alice"
    assert user.password_hash == "hashed-pw"
    assert user.target_lang == "fra"
    assert user.is_absolute_beginner is False


def test__create_user_absolute_beginner_flag() -> None:
    user = create_user("bob", "hashed-pw", "Bob", "eng", "fra", is_absolute_beginner=True)

    assert user.is_absolute_beginner is True


def test__get_user_by_username_found_and_missing() -> None:
    created = create_user("carla", "hashed-pw", "Carla", "eng", "fra")

    assert get_user_by_username("carla") == created
    assert get_user_by_username("nobody") is None


def test__get_user_by_id_found_and_missing() -> None:
    created = create_user("dana", "hashed-pw", "Dana", "eng", "fra")

    assert get_user_by_id(created.id) == created
    assert get_user_by_id(999) is None


def test__set_interests_replaces_previous_set() -> None:
    user = create_user("erin", "hashed-pw", "Erin", "eng", "fra")
    set_interests(user.id, {"hiking": 2.0, "cooking": 1.0})

    set_interests(user.id, {"chess": 3.0})

    assert get_interests(user.id) == {"chess": 3.0}


def test__get_interests_empty_for_new_user() -> None:
    user = create_user("finn", "hashed-pw", "Finn", "eng", "fra")

    assert get_interests(user.id) == {}


def test__create_user_email_defaults_to_none_and_can_be_set() -> None:
    without_email = create_user("gus", "hashed-pw", "Gus", "eng", "fra")
    with_email = create_user("holly", "hashed-pw", "Holly", "eng", "fra", email="holly@example.com")

    assert without_email.email is None
    assert with_email.email == "holly@example.com"


def test__list_all_users_includes_everyone() -> None:
    create_user("ida", "hashed-pw", "Ida", "eng", "fra")
    create_user("jack", "hashed-pw", "Jack", "eng", "fra")

    usernames = {u.username for u in list_all_users()}

    assert {"ida", "jack"} <= usernames


def test__set_last_proactive_sent_at_roundtrip() -> None:
    user = create_user("kim", "hashed-pw", "Kim", "eng", "fra")
    assert user.last_proactive_sent_at is None

    set_last_proactive_sent_at(user.id, "2026-01-01T00:00:00Z")

    assert get_user_by_id(user.id).last_proactive_sent_at == "2026-01-01T00:00:00Z"  # type: ignore[union-attr]
