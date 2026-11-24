from __future__ import annotations

import json

from pydantic import BaseModel

from app.db.models import Persona, SkillItem
from app.llm.client import LLMClient
from app.logging import get_logger

log = get_logger(__name__)


class _AuthenticityVerdict(BaseModel):
    is_authentic: bool
    rewritten_reply: str


def _build_verification_prompt(persona: Persona, draft_reply: str, focus_items: list[SkillItem]) -> tuple[str, str]:
    focus_desc = ", ".join(item.content for item in focus_items)
    system_prompt = (
        f"You review one draft reply from {persona.name}, a language-learning conversation partner who is "
        "secretly also a teacher - every reply is supposed to naturally work in some specific content, but it "
        "must still read as a completely ordinary, authentic message between two people, never as a lesson, "
        "quiz, or review session. Judge the draft against this priority order: sounding like a real, "
        f"interesting message in {persona.name}'s own voice comes FIRST; genuinely touching on the content "
        "comes second. A reply that's authentic but misses the content is better than one that's stilted but "
        f"hits it. The content this turn should be touching on: {focus_desc}. If the draft already reads as "
        "authentic by that priority order, return it completely unchanged. If it reads too much like a drill, "
        "a lesson announcement, or breaks character, rewrite it minimally - same voice, same core meaning, "
        "just make it sound like something a real person would actually say, dropping the content entirely if "
        'that\'s what authenticity requires. Respond with JSON only: {"is_authentic": bool, "rewritten_reply": '
        "str} - rewritten_reply is the original text verbatim if is_authentic is true, or your rewrite if false."
    )
    user_prompt = f"Draft reply:\n{draft_reply}"
    return system_prompt, user_prompt


def verify_and_rephrase(llm: LLMClient, persona: Persona, draft_reply: str, focus_items: list[SkillItem]) -> str:
    """A second, independent review pass over a persona's drafted reply - run only when this turn
    actually has teaching content riding on it (see `focus_items`); skipped otherwise, since a
    reply with nothing to smuggle in has nothing to check for didacticism. Never raises: an
    unparseable verdict just means the original draft goes out unreviewed, logged at warning - the
    same documented-fallback convention as `signals.extract_outcomes`."""
    if not focus_items:
        return draft_reply
    system_prompt, user_prompt = _build_verification_prompt(persona, draft_reply, focus_items)
    raw = llm.judge(system_prompt, user_prompt)
    try:
        verdict = _AuthenticityVerdict.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        log.warning("authenticity verification returned unparseable output, keeping draft unreviewed: %r", raw)
        return draft_reply
    return verdict.rewritten_reply
