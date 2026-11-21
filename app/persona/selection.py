from __future__ import annotations

import random

from app.db.conversations import get_most_recent_persona_id, list_conversations
from app.db.models import Persona, User
from app.db.personas import get_beginner_teacher_persona, list_personas
from app.persona.candidate_interests import sensitive_topics


def is_first_conversation(user: User) -> bool:
    return len(list_conversations(user.id)) == 0


def select_persona(user: User) -> Persona:
    """The absolute-beginner's very first conversation goes to the dedicated beginner-teacher
    persona; every other conversation (including a former beginner's second one onward) draws
    from the regular roster, avoiding whichever persona was used most recently for variety."""
    if user.is_absolute_beginner and is_first_conversation(user):
        beginner_teacher = get_beginner_teacher_persona(user.target_lang)
        if beginner_teacher is not None:
            return beginner_teacher

    roster = list_personas(user.target_lang)
    if not roster:
        raise ValueError(f"no personas exist for target_lang={user.target_lang!r} - run generate_personas.py first")

    most_recent_id = get_most_recent_persona_id(user.id)
    candidates = [p for p in roster if p.id != most_recent_id] or roster
    return random.choice(candidates)


def shared_interest(persona: Persona, user_interests: dict[str, float]) -> tuple[str, bool]:
    """(topic, True) for a genuinely shared interest (the user's highest-weighted one this
    persona also has), or (topic, False) falling back to the user's top interest when there's no
    overlap - the bool tells the prompt builder which framing to use. Political/religious topics
    are excluded even if coincidentally shared - that's exactly what a persona shouldn't volunteer
    as small talk per the taboo-handling guardrail."""
    sensitive = sensitive_topics()
    safe_user_interests = {topic: weight for topic, weight in user_interests.items() if topic not in sensitive}
    if not safe_user_interests:
        raise ValueError("cannot compute a shared interest with no non-sensitive user interests configured")
    overlap = [topic for topic in persona.interests if topic in safe_user_interests]
    if overlap:
        best = max(overlap, key=lambda topic: safe_user_interests[topic])
        return best, True
    top_user_interest = max(safe_user_interests, key=lambda topic: safe_user_interests[topic])
    return top_user_interest, False
