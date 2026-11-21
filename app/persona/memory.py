from __future__ import annotations

from app.config import settings
from app.db.conversations import get_messages_with_persona_after
from app.db.models import Persona, User
from app.db.persona_memory import get_memory, upsert_memory
from app.llm.client import LLMClient

_SUMMARIZATION_TIMEOUT_SECONDS = 120


def _build_summarization_prompt(persona: Persona, previous_summary: str, transcript: str) -> tuple[str, str]:
    system_prompt = (
        f"You are {persona.name}, a {persona.age}-year-old from {persona.origin} with this "
        f"personality: {persona.psychological_profile}. You're updating your private memory of "
        "one specific person you've been talking with, after one or more conversations. Write an "
        "updated summary (plain prose) covering: (1) what you told them about yourself that you "
        "should stay consistent with later, (2) what they told you about themselves, and (3) your "
        "own honest, personality-driven feelings and judgment about them as a person - not just "
        f"facts. Keep the WHOLE summary under {settings.relationship_summary_max_words} words - "
        "memory is lossy by nature, so if new material would push you over that, let the least "
        "important or least-reinforced older details fade rather than making the summary longer; "
        "keep whatever still feels relevant or emotionally significant. Respond with the updated "
        "summary text only, nothing else."
    )
    user_prompt = (
        f"Your current memory of this person: {previous_summary or '(you have not met them before)'}\n\n"
        f"New conversation transcript to fold in:\n{transcript}"
    )
    return system_prompt, user_prompt


def sync_relationship_memory(llm: LLMClient, user: User, persona: Persona) -> str:
    """Fold any of this user's messages with `persona` since the last sync into that persona's
    running memory of this user, and return the (possibly just-updated) summary. A no-op, aside
    from a read, when there's nothing new since last time."""
    memory = get_memory(user.id, persona.id)
    after_id = memory.last_summarized_message_id or 0
    new_messages = get_messages_with_persona_after(user.id, persona.id, after_id)
    if not new_messages:
        return memory.summary

    transcript = "\n".join(f"{m.role}: {m.text}" for m in new_messages)
    system_prompt, user_prompt = _build_summarization_prompt(persona, memory.summary, transcript)
    new_summary = llm.judge(system_prompt, user_prompt, timeout_seconds=_SUMMARIZATION_TIMEOUT_SECONDS)

    upsert_memory(user.id, persona.id, new_summary, last_summarized_message_id=new_messages[-1].id)
    return new_summary
