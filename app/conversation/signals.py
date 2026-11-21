from __future__ import annotations

import json

from pydantic import BaseModel

from app.db.conversations import add_item_event
from app.db.memory import get_state, upsert_state
from app.db.models import ItemOutcome, SkillItem
from app.llm.client import LLMClient
from app.logging import get_logger
from app.srs.scheduler import MemoryRating, introduce, review

log = get_logger(__name__)

_RATING_BY_OUTCOME: dict[ItemOutcome, MemoryRating] = {
    "correct": "easy",
    "hesitant": "good",
    "incorrect": "hard",
    "avoided": "again",
}


class ItemOutcomeEntry(BaseModel):
    item_id: int
    outcome: ItemOutcome


class JudgeResult(BaseModel):
    outcomes: list[ItemOutcomeEntry]


def _build_judge_prompt(target_items: list[SkillItem], user_message: str) -> tuple[str, str]:
    # Mechanical classification prompt, not the conversational/teaching prompt - placeholder
    # wording, to be refined once the teaching methodology itself is designed.
    items_desc = "\n".join(f"- id={item.id}: {item.content} ({item.type})" for item in target_items)
    system_prompt = (
        "You classify how a language learner used specific target items in one message. "
        'Respond with JSON only, matching: {"outcomes": [{"item_id": int, '
        '"outcome": "correct"|"hesitant"|"incorrect"|"avoided"}]}. '
        "Only include items that were actually relevant to this message; omit the rest."
    )
    user_prompt = f"Target items:\n{items_desc}\n\nLearner's message:\n{user_message}"
    return system_prompt, user_prompt


def extract_outcomes(llm: LLMClient, target_items: list[SkillItem], user_message: str) -> list[ItemOutcomeEntry]:
    if not target_items:
        return []
    system_prompt, prompt = _build_judge_prompt(target_items, user_message)
    raw = llm.judge(system_prompt, prompt)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("judge call returned non-JSON output, skipping signal extraction: %r", raw)
        return []
    return JudgeResult.model_validate(payload).outcomes


def apply_outcomes(user_id: int, message_id: int, outcomes: list[ItemOutcomeEntry]) -> None:
    for entry in outcomes:
        add_item_event(message_id, entry.item_id, entry.outcome)
        state = get_state(user_id, entry.item_id) or introduce(user_id, entry.item_id)
        updated = review(state, _RATING_BY_OUTCOME[entry.outcome])
        upsert_state(updated)
