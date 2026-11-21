from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from app.config import settings
from app.curriculum.selection import select_frontier_items, select_topic
from app.db.conversations import get_recent_topics
from app.db.memory import get_chronic_issue_states, get_due_items, get_introduced_item_ids, get_mastered_states
from app.db.models import SkillItem, User
from app.db.skills import list_skill_items
from app.db.users import get_interests


class LearnerProfileSummary(BaseModel):
    known_item_count: int
    known_categories: dict[str, int]
    chronic_issue_items: list[SkillItem]


class SessionPlan(BaseModel):
    user: User
    topic: str
    due_items: list[SkillItem]
    new_items: list[SkillItem]
    learner_profile: LearnerProfileSummary


def _build_learner_profile(all_items_by_id: dict[int, SkillItem], user_id: int, now_iso: str) -> LearnerProfileSummary:
    mastered_states = get_mastered_states(user_id, now_iso)
    known_categories: dict[str, int] = {}
    for state in mastered_states:
        item = all_items_by_id.get(state.item_id)
        if item is None:
            continue
        category = item.category or "uncategorized"
        known_categories[category] = known_categories.get(category, 0) + 1

    # get_chronic_issue_states already orders by lapses DESC - take the worst few, not all of
    # them ever accumulated, so this doesn't grow without bound as a long-term user racks up
    # chronic items across months of use.
    chronic_states = get_chronic_issue_states(user_id)[: settings.max_chronic_items_shown]
    chronic_items = [all_items_by_id[state.item_id] for state in chronic_states if state.item_id in all_items_by_id]

    return LearnerProfileSummary(
        known_item_count=len(mastered_states),
        known_categories=known_categories,
        chronic_issue_items=chronic_items,
    )


def build_session_plan(user: User) -> SessionPlan:
    """Decide what this session should cover: due reviews, at most a couple of new items, a
    topic of interest, and a summary of what the learner already knows / struggles with -
    all of it structure for the conversation layer to build on, not the conversation itself."""
    now_iso = datetime.now(UTC).isoformat()
    all_items = list_skill_items(user.target_lang)
    all_items_by_id = {item.id: item for item in all_items}

    introduced_ids = get_introduced_item_ids(user.id)
    # get_due_items orders by due_at ASC (most overdue first) - cap it, both because a long gap
    # between sessions could otherwise pile up dozens of due items in one prompt, and because
    # reviewing dozens of things in one natural conversation isn't realistic anyway.
    due_states = get_due_items(user.id, now_iso)[: settings.max_due_items_per_session]
    due_items = [all_items_by_id[state.item_id] for state in due_states if state.item_id in all_items_by_id]

    new_items = select_frontier_items(all_items, introduced_ids, max_new=settings.new_items_per_session)

    interests = get_interests(user.id)
    recent_topics = get_recent_topics(user.id)
    topic = select_topic(interests, recent_topics)

    learner_profile = _build_learner_profile(all_items_by_id, user.id, now_iso)

    return SessionPlan(
        user=user,
        topic=topic,
        due_items=due_items,
        new_items=new_items,
        learner_profile=learner_profile,
    )
