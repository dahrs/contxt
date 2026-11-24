from __future__ import annotations

import random

import pytest

from app.curriculum.selection import compute_unlocked_milestones, select_frontier_items, select_topic
from app.db.models import Milestone, SkillItem


def _item(id_: int, milestone_id: int = 1, prerequisite_ids: list[int] | None = None) -> SkillItem:
    return SkillItem(
        id=id_,
        type="vocab",
        native_lang="eng",
        target_lang="fra",
        content=f"item-{id_}",
        milestone_id=milestone_id,
        prerequisite_ids=prerequisite_ids or [],
    )


def _milestone(id_: int, prerequisite_ids: list[int] | None = None) -> Milestone:
    return Milestone(
        id=id_, name=f"milestone-{id_}", description="d", cefr_level="A1", prerequisite_ids=prerequisite_ids or []
    )


def test__select_frontier_items_excludes_already_introduced() -> None:
    items = [_item(1), _item(2)]

    frontier = select_frontier_items(items, introduced_ids={1}, unlocked_milestone_ids={1}, max_new=10)

    assert [i.id for i in frontier] == [2]


def test__select_frontier_items_excludes_items_with_unmet_prerequisites() -> None:
    items = [_item(1), _item(2, prerequisite_ids=[1])]

    frontier = select_frontier_items(items, introduced_ids=set(), unlocked_milestone_ids={1}, max_new=10)

    assert [i.id for i in frontier] == [1]


def test__select_frontier_items_includes_item_once_its_prerequisite_is_introduced() -> None:
    items = [_item(1), _item(2, prerequisite_ids=[1])]

    frontier = select_frontier_items(items, introduced_ids={1}, unlocked_milestone_ids={1}, max_new=10)

    assert [i.id for i in frontier] == [2]


def test__select_frontier_items_respects_max_new_cap() -> None:
    items = [_item(1), _item(2), _item(3)]

    frontier = select_frontier_items(items, introduced_ids=set(), unlocked_milestone_ids={1}, max_new=2)

    assert len(frontier) == 2


def test__select_frontier_items_excludes_items_in_a_locked_milestone() -> None:
    items = [_item(1, milestone_id=1), _item(2, milestone_id=2)]

    frontier = select_frontier_items(items, introduced_ids=set(), unlocked_milestone_ids={1}, max_new=10)

    assert [i.id for i in frontier] == [1]


def test__compute_unlocked_milestones_always_unlocks_milestones_with_no_prerequisites() -> None:
    milestones = [_milestone(1)]

    assert compute_unlocked_milestones(milestones, introduced_counts={}, total_counts={}, threshold=0.7) == {1}


def test__compute_unlocked_milestones_requires_threshold_met_on_every_prerequisite() -> None:
    milestones = [_milestone(1), _milestone(2, prerequisite_ids=[1])]

    locked = compute_unlocked_milestones(milestones, introduced_counts={1: 3}, total_counts={1: 10}, threshold=0.7)
    assert locked == {1}  # 2 stays locked: only 30% of its prerequisite introduced

    unlocked = compute_unlocked_milestones(milestones, introduced_counts={1: 8}, total_counts={1: 10}, threshold=0.7)
    assert unlocked == {1, 2}  # 80% >= 70% threshold


def test__compute_unlocked_milestones_treats_a_prerequisite_with_no_content_as_unmet() -> None:
    milestones = [_milestone(1), _milestone(2, prerequisite_ids=[1])]

    # total_counts has no entry for milestone 1 - no skill_items generated for it yet. Milestone
    # 1 itself still unlocks unconditionally (no prerequisites), but 2 can't, since 0/1 < 0.7.
    unlocked = compute_unlocked_milestones(milestones, introduced_counts={}, total_counts={}, threshold=0.7)

    assert unlocked == {1}


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
