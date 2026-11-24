from __future__ import annotations

from app.db.milestones import create_milestone
from app.db.skills import create_skill_item, get_skill_item, list_skill_items


def _milestone_id() -> int:
    return create_milestone("Greetings", "Can greet someone", "A1").id


def test__create_skill_item_roundtrip() -> None:
    milestone_id = _milestone_id()
    item = create_skill_item("vocab", "eng", "fra", "bonjour", milestone_id)

    assert item.type == "vocab"
    assert item.native_lang == "eng"
    assert item.content == "bonjour"
    assert item.milestone_id == milestone_id
    assert item.prerequisite_ids == []


def test__create_skill_item_with_prerequisites() -> None:
    milestone_id = _milestone_id()
    greet = create_skill_item("vocab", "eng", "fra", "bonjour", milestone_id)
    farewell = create_skill_item("vocab", "eng", "fra", "au revoir", milestone_id, prerequisite_ids=[greet.id])

    assert farewell.prerequisite_ids == [greet.id]


def test__get_skill_item_missing_returns_none() -> None:
    assert get_skill_item(999) is None


def test__list_skill_items_filters_by_native_and_target_lang() -> None:
    milestone_id = _milestone_id()
    create_skill_item("vocab", "eng", "fra", "bonjour", milestone_id)
    create_skill_item("vocab", "eng", "spa", "hola", milestone_id)
    create_skill_item("vocab", "deu", "fra", "bonjour (from German)", milestone_id)

    fra_items = list_skill_items("eng", "fra")

    assert len(fra_items) == 1
    assert fra_items[0].content == "bonjour"
