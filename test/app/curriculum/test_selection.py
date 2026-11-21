from __future__ import annotations

import random

import pytest

from app.curriculum.selection import select_frontier_items, select_topic
from app.db.models import SkillItem


def _item(id_: int, level: str = "A1", prerequisite_ids: list[int] | None = None) -> SkillItem:
    return SkillItem(
        id=id_,
        type="vocab",
        target_lang="fra",
        content=f"item-{id_}",
        level=level,
        category=None,
        prerequisite_ids=prerequisite_ids or [],
    )


def test__select_frontier_items_excludes_already_introduced() -> None:
    items = [_item(1), _item(2)]

    frontier = select_frontier_items(items, introduced_ids={1}, max_new=10)

    assert [i.id for i in frontier] == [2]


def test__select_frontier_items_excludes_items_with_unmet_prerequisites() -> None:
    items = [_item(1), _item(2, prerequisite_ids=[1])]

    frontier = select_frontier_items(items, introduced_ids=set(), max_new=10)

    assert [i.id for i in frontier] == [1]


def test__select_frontier_items_includes_item_once_its_prerequisite_is_introduced() -> None:
    items = [_item(1), _item(2, prerequisite_ids=[1])]

    frontier = select_frontier_items(items, introduced_ids={1}, max_new=10)

    assert [i.id for i in frontier] == [2]


def test__select_frontier_items_respects_max_new_cap() -> None:
    items = [_item(1), _item(2), _item(3)]

    frontier = select_frontier_items(items, introduced_ids=set(), max_new=2)

    assert len(frontier) == 2


def test__select_topic_raises_with_no_interests() -> None:
    with pytest.raises(ValueError):
        select_topic({}, recent_topics=[])


def test__select_topic_discounts_recently_used_topics(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_choices(population: list[str], weights: list[float], k: int) -> list[str]:
        captured["population"] = population
        captured["weights"] = weights
        return [population[0]]

    monkeypatch.setattr(random, "choices", fake_choices)

    select_topic({"travel": 2.0, "cooking": 2.0}, recent_topics=["travel"])

    population = captured["population"]
    weights = captured["weights"]
    assert isinstance(population, list) and isinstance(weights, list)
    travel_weight = weights[population.index("travel")]
    cooking_weight = weights[population.index("cooking")]
    assert travel_weight < cooking_weight
