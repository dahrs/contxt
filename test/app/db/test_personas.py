from __future__ import annotations

import pytest

from app.db.personas import create_persona, delete_persona, get_beginner_teacher_persona, get_persona, list_personas
from test.factories import make_persona as _make


def _minimal_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "target_lang": "fra",
        "name": "Test",
        "origin": "N/A",
        "age": 30,
        "background": "N/A",
        "physical_description": "N/A",
        "psychological_profile": "N/A",
        "social_habits": "N/A",
        "explanation_style": "N/A",
        "teaching_philosophy": "N/A",
        "correction_style": "N/A",
        "preferred_medium": "N/A",
        "vocabulary_strictness": "N/A",
        "cultural_depth": "N/A",
        "timezone": "UTC",
        "daily_routine": "N/A",
        "free_hours": [19, 20],
        "interests": [],
    }
    defaults.update(overrides)
    return defaults


def test__create_persona_roundtrip_with_interests() -> None:
    persona = _make(interests=["hiking", "chess"])

    # persona_interests has no defined order - nothing in the app relies on insertion order.
    assert set(persona.interests) == {"hiking", "chess"}
    assert get_persona(persona.id) == persona


def test__create_persona_roundtrips_free_hours() -> None:
    persona = create_persona(**_minimal_kwargs(free_hours=[7, 19, 23]))  # type: ignore[arg-type]

    assert persona.free_hours == [7, 19, 23]


def test__create_persona_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        create_persona(**_minimal_kwargs(timezone="Not/AZone"))  # type: ignore[arg-type]


def test__create_persona_rejects_out_of_range_free_hours() -> None:
    with pytest.raises(ValueError, match="free_hours"):
        create_persona(**_minimal_kwargs(free_hours=[7, 24]))  # type: ignore[arg-type]


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
