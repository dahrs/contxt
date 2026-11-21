from __future__ import annotations

from app.db.personas import delete_persona, get_beginner_teacher_persona, get_persona, list_personas
from test.factories import make_persona as _make


def test__create_persona_roundtrip_with_interests() -> None:
    persona = _make(interests=["hiking", "chess"])

    # persona_interests has no defined order - nothing in the app relies on insertion order.
    assert set(persona.interests) == {"hiking", "chess"}
    assert get_persona(persona.id) == persona


def test__get_persona_missing_returns_none() -> None:
    assert get_persona(999) is None


def test__list_personas_excludes_beginner_teacher_and_other_languages() -> None:
    regular = _make(target_lang="fra")
    _make(target_lang="fra", is_beginner_teacher=True)
    _make(target_lang="spa")

    roster = list_personas("fra")

    assert [p.id for p in roster] == [regular.id]


def test__get_beginner_teacher_persona_found_and_missing() -> None:
    assert get_beginner_teacher_persona("fra") is None

    teacher = _make(target_lang="fra", is_beginner_teacher=True)

    assert get_beginner_teacher_persona("fra") == teacher


def test__delete_persona_removes_it() -> None:
    persona = _make()
    delete_persona(persona.id)

    assert get_persona(persona.id) is None
