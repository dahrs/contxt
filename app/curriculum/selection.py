from __future__ import annotations

import random

from app.db.models import Milestone, SkillItem

_RECENCY_PENALTY = 0.3


def compute_unlocked_milestones(
    milestones: list[Milestone], introduced_counts: dict[int, int], total_counts: dict[int, int], threshold: float
) -> set[int]:
    """A milestone with no prerequisites is always unlocked. Otherwise it unlocks once every
    prerequisite milestone has *introduced* (not necessarily mastered - FSRS mastery is an
    ongoing moving target, gating on perfect retention would stall progress) at least `threshold`
    of its own items. total_counts.get(id, 1) defaults the denominator to 1 (not 0) so a
    prerequisite with no generated content yet doesn't produce a division error or a vacuous
    unlock - it just can't be satisfied until content exists for it."""
    unlocked: set[int] = set()
    for milestone in milestones:
        if not milestone.prerequisite_ids:
            unlocked.add(milestone.id)
            continue
        ratios_met = all(
            introduced_counts.get(prereq_id, 0) / total_counts.get(prereq_id, 1) >= threshold
            for prereq_id in milestone.prerequisite_ids
        )
        if ratios_met:
            unlocked.add(milestone.id)
    return unlocked


def select_frontier_items(
    all_items: list[SkillItem], introduced_ids: set[int], unlocked_milestone_ids: set[int], max_new: int
) -> list[SkillItem]:
    """Items not yet introduced, whose own prerequisites are already introduced, *and* whose
    milestone is unlocked - the milestone DAG and the item DAG both have to clear."""
    frontier = [
        item
        for item in all_items
        if item.id not in introduced_ids
        and item.milestone_id in unlocked_milestone_ids
        and all(prereq_id in introduced_ids for prereq_id in item.prerequisite_ids)
    ]
    # Milestones are generated in dependency order, so id order is already a reasonable proxy
    # for sequencing - this only needs to be a stable tie-break, not a perfect topological sort.
    frontier.sort(key=lambda item: (item.milestone_id, item.id))
    return frontier[:max_new]


def select_topic(interests: dict[str, float], recent_topics: list[str]) -> str:
    """Weighted pick of a topic of interest, with a novelty discount for recently-used topics."""
    if not interests:
        raise ValueError("cannot select a topic with no interests configured")
    topics = list(interests.keys())
    weights = [interests[topic] * (_RECENCY_PENALTY if topic in recent_topics else 1.0) for topic in topics]
    return random.choices(topics, weights=weights, k=1)[0]
