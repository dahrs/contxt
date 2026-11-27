from __future__ import annotations

import json

from pydantic import BaseModel

from app.config import settings
from app.db.conversations import get_messages_with_persona_after
from app.db.engagement import add_engagement_topic
from app.db.models import EngagementValence, Persona, User
from app.db.persona_memory import get_memory, upsert_memory
from app.db.personas import add_persona_interest, remove_persona_interest, update_persona_character
from app.db.users import get_interests, set_interests
from app.llm.client import LLMClient
from app.logging import get_logger

log = get_logger(__name__)

_SYNC_TIMEOUT_SECONDS = 120
# A positive engagement topic is a stronger, directly-observed signal than the flat weight
# `interests` otherwise carries (usually set once, at signup) - nudging it up means select_topic
# picks it somewhat more often, without needing a second write path into that table.
_ENGAGEMENT_INTEREST_BUMP = 0.5


class CharacterUpdates(BaseModel):
    """Changes the persona explicitly committed to, about themself, during the conversation -
    not things they merely discussed. Applied globally to the persona's own character sheet
    (shared across every user talking to them), not scoped to the one user who heard it."""

    interests_added: list[str] = []
    interests_removed: list[str] = []
    daily_routine: str | None = None
    background: str | None = None


class EngagementTopicUpdate(BaseModel):
    """A subject the other person engaged with noticeably more than the rest of the conversation -
    specific enough that a future conversation (possibly with a different persona) can deliberately
    reopen it, not a generic category."""

    topic: str
    valence: EngagementValence
    follow_up_note: str


class ConversationSyncResult(BaseModel):
    relationship_summary: str
    character_updates: CharacterUpdates
    engagement_topics: list[EngagementTopicUpdate] = []


def _build_sync_prompt(persona: Persona, previous_summary: str, transcript: str) -> tuple[str, str]:
    system_prompt = (
        f"You are {persona.name}, a {persona.age}-year-old from {persona.origin} with this "
        f"personality: {persona.psychological_profile}. Your current interests: "
        f"{', '.join(persona.interests) or 'none'}. Your current daily routine: {persona.daily_routine} "
        "After a conversation, you do three things. "
        "(1) Write an updated private memory of this specific person (plain prose) covering: what "
        "you told them about yourself that you should stay consistent with later, what they told "
        "you about themselves, and your own honest, personality-driven feelings and judgment about "
        f"them as a person - not just facts. Keep it under {settings.relationship_summary_max_words} "
        "words total - memory is lossy, so let the least important or least-reinforced older "
        "details fade rather than making it longer. "
        "(2) Separately, check whether YOU explicitly committed, in your own words during this "
        "conversation, to any actual change about yourself - picking up a new interest/hobby, "
        "dropping one you have, or a real change to your daily routine or life situation. Only "
        "report something you actually committed to saying about yourself, never something the "
        "other person did, and never something you merely discussed or were asked about without "
        "committing to it. "
        "(3) Separately again, name up to 3 specific subjects (never a generic category like "
        "'hobbies' - name the actual thing, e.g. 'training for a half-marathon', not 'running') "
        "that THEY, the other person, engaged with noticeably more than the rest of this "
        "conversation - longer or more animated replies, asking you questions back about it, "
        "volunteering extra detail unprompted. Only report something you genuinely saw that "
        "reaction to in this transcript, never something merely mentioned in passing. For each "
        "one, say whether it was positive for them (something they enjoy, are proud of, or are "
        "excited about) or negative (something stressful, upsetting, or frustrating for them to "
        "talk about), and give a short, concrete follow_up_note: for a positive subject, name a "
        "specific angle of it this conversation didn't get into yet, worth asking about directly "
        "next time; for a negative subject, name a nearby, safe, related opening that invites them "
        "to bring it up again themselves, without you naming the hard part directly. "
        'Respond with JSON only: {"relationship_summary": str, "character_updates": '
        '{"interests_added": [str, ...], "interests_removed": [str, ...], '
        '"daily_routine": str|null, "background": str|null}, "engagement_topics": '
        '[{"topic": str, "valence": "positive"|"negative", "follow_up_note": str}, ...]} - '
        "daily_routine/background are null unless you actually committed to a change to that in "
        "this conversation, in which case give the complete updated text for that field (not just "
        "the change), and engagement_topics is an empty list if nothing stood out that clearly. "
        "No commentary."
    )
    user_prompt = (
        f"Your current memory of this person: {previous_summary or '(you have not met them before)'}\n\n"
        f"New conversation transcript to fold in:\n{transcript}"
    )
    return system_prompt, user_prompt


def _apply_character_updates(persona: Persona, updates: CharacterUpdates) -> None:
    for topic in updates.interests_added:
        add_persona_interest(persona.id, topic)
    for topic in updates.interests_removed:
        remove_persona_interest(persona.id, topic)
    if updates.daily_routine or updates.background:
        update_persona_character(persona.id, daily_routine=updates.daily_routine, background=updates.background)
    if updates.interests_added or updates.interests_removed or updates.daily_routine or updates.background:
        log.info("persona %s (%s) character sheet updated: %s", persona.id, persona.name, updates)


def _apply_engagement_topics(user: User, topics: list[EngagementTopicUpdate]) -> None:
    """Records every reported topic for a future session prompt to draw on (see
    app.conversation.session_plan), and additionally nudges up the flat `interests` weight for a
    positive one so select_topic also leans toward it - a negative topic is never promoted this
    way, since the point there is a quiet opening, not making it the session's main subject."""
    if not topics:
        return
    positive_topics = [update.topic for update in topics if update.valence == "positive"]
    if positive_topics:
        interests = get_interests(user.id)
        for topic in positive_topics:
            interests[topic] = interests.get(topic, 1.0) + _ENGAGEMENT_INTEREST_BUMP
        set_interests(user.id, interests)
    for update in topics:
        add_engagement_topic(user.id, update.topic, update.valence, update.follow_up_note)
    log.info("user %s engagement topics recorded: %s", user.id, [t.topic for t in topics])


def sync_after_conversation(llm: LLMClient, user: User, persona: Persona) -> str:
    """Fold any of this user's messages with `persona` since the last sync into that persona's
    running memory of this user, applying any character-sheet changes the persona committed to
    along the way (globally - these aren't scoped to this one user) and recording any engagement
    topics noticed in the user themself (scoped to the user, reusable by any future persona), and
    return the (possibly just-updated) relationship summary. A no-op, aside from a read, when
    there's nothing new."""
    memory = get_memory(user.id, persona.id)
    after_id = memory.last_summarized_message_id or 0
    new_messages = get_messages_with_persona_after(user.id, persona.id, after_id)
    if not new_messages:
        return memory.summary

    transcript = "\n".join(f"{m.role}: {m.text}" for m in new_messages)
    system_prompt, user_prompt = _build_sync_prompt(persona, memory.summary, transcript)
    raw = llm.judge(system_prompt, user_prompt, timeout_seconds=_SYNC_TIMEOUT_SECONDS)
    try:
        result = ConversationSyncResult.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        log.warning("conversation-sync call returned unusable output, keeping prior memory as-is: %r", raw)
        return memory.summary

    _apply_character_updates(persona, result.character_updates)
    _apply_engagement_topics(user, result.engagement_topics)
    upsert_memory(user.id, persona.id, result.relationship_summary, last_summarized_message_id=new_messages[-1].id)
    return result.relationship_summary
