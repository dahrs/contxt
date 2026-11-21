from __future__ import annotations

import random

from app.db.models import SkillItem

_RECENCY_PENALTY = 0.3


def select_frontier_items(all_items: list[SkillItem], introduced_ids: set[int], max_new: int) -> list[SkillItem]:
    """Items not yet introduced whose prerequisites are all already introduced."""
    frontier = [
        item
        for item in all_items
        if item.id not in introduced_ids and all(prereq_id in introduced_ids for prereq_id in item.prerequisite_ids)
    ]
    frontier.sort(key=lambda item: (item.level, item.id))
    return frontier[:max_new]


def select_topic(interests: dict[str, float], recent_topics: list[str]) -> str:
    """Weighted pick of a topic of interest, with a novelty discount for recently-used topics."""
    if not interests:
        raise ValueError("cannot select a topic with no interests configured")
    topics = list(interests.keys())
    weights = [interests[topic] * (_RECENCY_PENALTY if topic in recent_topics else 1.0) for topic in topics]
    return random.choices(topics, weights=weights, k=1)[0]
