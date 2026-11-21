from __future__ import annotations

from app.db.skills import create_skill_item, get_skill_item, list_skill_items


def test__create_skill_item_roundtrip() -> None:
    item = create_skill_item("vocab", "fra", "bonjour", "A1", category="greetings")

    assert item.type == "vocab"
    assert item.content == "bonjour"
    assert item.category == "greetings"
    assert item.prerequisite_ids == []


def test__create_skill_item_with_prerequisites() -> None:
    greet = create_skill_item("vocab", "fra", "bonjour", "A1")
    farewell = create_skill_item("vocab", "fra", "au revoir", "A1", prerequisite_ids=[greet.id])

    assert farewell.prerequisite_ids == [greet.id]


def test__get_skill_item_missing_returns_none() -> None:
    assert get_skill_item(999) is None


def test__list_skill_items_filters_by_target_lang() -> None:
    create_skill_item("vocab", "fra", "bonjour", "A1")
    create_skill_item("vocab", "spa", "hola", "A1")

    fra_items = list_skill_items("fra")

    assert len(fra_items) == 1
    assert fra_items[0].content == "bonjour"
