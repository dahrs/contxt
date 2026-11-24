from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from app.config import settings
from app.curriculum.selection import compute_unlocked_milestones, select_frontier_items, select_topic
from app.db.conversations import get_recent_topics
from app.db.memory import get_chronic_issue_states, get_due_items, get_introduced_item_ids, get_mastered_states
from app.db.milestones import get_introduced_counts_by_milestone, get_milestone_item_counts, list_milestones
from app.db.models import Milestone, SkillItem, User
from app.db.skills import list_skill_items
from app.db.users import get_interests


class LearnerProfileSummary(BaseModel):
    known_item_count: int
    known_milestones: dict[str, int]
    chronic_issue_items: list[SkillItem]


class SessionPlan(BaseModel):
    user: User
    topic: str
    due_items: list[SkillItem]
    new_items: list[SkillItem]
    current_milestone: Milestone | None
    learner_profile: LearnerProfileSummary


def _build_learner_profile(
    all_items_by_id: dict[int, SkillItem], milestones_by_id: dict[int, Milestone], user_id: int, now_iso: str
) -> LearnerProfileSummary:
    mastered_states = get_mastered_states(user_id, now_iso)
    known_milestones: dict[str, int] = {}
    for state in mastered_states:
        item = all_items_by_id.get(state.item_id)
        if item is None:
            continue
        milestone = milestones_by_id.get(item.milestone_id)
        name = milestone.name if milestone is not None else "uncategorized"
        known_milestones[name] = known_milestones.get(name, 0) + 1

    # get_chronic_issue_states already orders by lapses DESC - take the worst few, not all of
    # them ever accumulated, so this doesn't grow without bound as a long-term user racks up
    # chronic items across months of use.
    chronic_states = get_chronic_issue_states(user_id)[: settings.max_chronic_items_shown]
    chronic_items = [all_items_by_id[state.item_id] for state in chronic_states if state.item_id in all_items_by_id]

    return LearnerProfileSummary(
        known_item_count=len(mastered_states),
        known_milestones=known_milestones,
        chronic_issue_items=chronic_items,
    )


def _current_milestone(
    milestones: list[Milestone], unlocked_ids: set[int], introduced_counts: dict[int, int], total_counts: dict[int, int]
) -> Milestone | None:
    """Among unlocked milestones, whichever has the lowest introduced-ratio that's still below
    1.0 - the one actively "in progress" right now. None if everything unlocked is already
    fully introduced (nothing left to be "working on" yet, beyond ongoing review)."""
    in_progress = [
        m for m in milestones if m.id in unlocked_ids and introduced_counts.get(m.id, 0) < total_counts.get(m.id, 0)
    ]
    if not in_progress:
        return None
    return min(in_progress, key=lambda m: introduced_counts.get(m.id, 0) / total_counts.get(m.id, 1))


def build_session_plan(user: User) -> SessionPlan:
    """Decide what this session should cover: due reviews, at most a couple of new items, a
    topic of interest, and a summary of what the learner already knows / struggles with -
    all of it structure for the conversation layer to build on, not the conversation itself."""
    now_iso = datetime.now(UTC).isoformat()
    all_items = list_skill_items(user.native_lang, user.target_lang)
    all_items_by_id = {item.id: item for item in all_items}
    milestones = list_milestones()
    milestones_by_id = {m.id: m for m in milestones}

    introduced_ids = get_introduced_item_ids(user.id)
    # get_due_items orders by due_at ASC (most overdue first) - cap it, both because a long gap
    # between sessions could otherwise pile up dozens of due items in one prompt, and because
    # reviewing dozens of things in one natural conversation isn't realistic anyway.
    due_states = get_due_items(user.id, now_iso)[: settings.max_due_items_per_session]
    due_items = [all_items_by_id[state.item_id] for state in due_states if state.item_id in all_items_by_id]

    total_counts = get_milestone_item_counts(user.native_lang, user.target_lang)
    introduced_counts = get_introduced_counts_by_milestone(user.id, user.native_lang, user.target_lang)
    unlocked_ids = compute_unlocked_milestones(
        milestones, introduced_counts, total_counts, settings.milestone_unlock_threshold
    )
    new_items = select_frontier_items(all_items, introduced_ids, unlocked_ids, max_new=settings.new_items_per_session)
    current_milestone = _current_milestone(milestones, unlocked_ids, introduced_counts, total_counts)

    interests = get_interests(user.id)
    recent_topics = get_recent_topics(user.id)
    topic = select_topic(interests, recent_topics)

    learner_profile = _build_learner_profile(all_items_by_id, milestones_by_id, user.id, now_iso)

    return SessionPlan(
        user=user,
        topic=topic,
        due_items=due_items,
        new_items=new_items,
        current_milestone=current_milestone,
        learner_profile=learner_profile,
    )
