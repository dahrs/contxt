from __future__ import annotations

import json
import sys

from pydantic import BaseModel

from app.db.connection import init_db
from app.db.milestones import create_milestone
from app.llm import get_llm_client
from app.logging import get_logger

log = get_logger(__name__)

_GENERATION_TIMEOUT_SECONDS = 300


class _GeneratedMilestone(BaseModel):
    key: str
    name: str
    description: str
    cefr_level: str
    prerequisite_keys: list[str] = []


class _GeneratedBatch(BaseModel):
    milestones: list[_GeneratedMilestone]


def _build_prompt() -> tuple[str, str]:
    system_prompt = (
        "You design the language-independent skeleton of a communicative-function curriculum for "
        "a conversational language-learning app - a sequence of milestones any learner works "
        "through regardless of which language they're learning (the actual vocabulary/grammar "
        "content is generated separately, per language, against this skeleton). Generate 15-20 "
        "milestones spanning roughly CEFR A1 through B1/B2, starting from the most basic "
        "(classroom language - phrases needed to participate in a lesson at all - then greetings, "
        "then basic transactional interactions like asking for services or buying something) and "
        "building up from there (introducing yourself, talking about daily routines, giving "
        "directions, making plans, expressing opinions, telling stories in the past, etc. - use "
        "your own judgment for a sensible, real progression). Each milestone needs: key (a short "
        "unique snake_case identifier, e.g. 'classroom_language'), name (a few words), description "
        "(one sentence naming the concrete communicative goal, e.g. 'Can order food and ask for "
        "the bill'), cefr_level (e.g. 'A1'), and prerequisite_keys (the keys of milestones that "
        "must come first - empty for genuinely foundational ones like classroom language and "
        "greetings; most later milestones should depend on at least one earlier one, but it's a "
        "DAG, not a strict line - independent milestones can share the same prerequisites). "
        "List milestones in dependency order (every prerequisite_key must refer to a milestone "
        "already listed earlier in the array). "
        'Respond with JSON only: {"milestones": [{...}, ...]}, no commentary.'
    )
    return system_prompt, "Generate the milestone sequence now."


def main() -> int:
    try:
        init_db()
        system_prompt, user_prompt = _build_prompt()
        raw = get_llm_client().judge(system_prompt, user_prompt, timeout_seconds=_GENERATION_TIMEOUT_SECONDS)
        batch = _GeneratedBatch.model_validate(json.loads(raw))

        key_to_id: dict[str, int] = {}
        for generated in batch.milestones:
            missing = [key for key in generated.prerequisite_keys if key not in key_to_id]
            if missing:
                raise ValueError(
                    f"milestone {generated.key!r} references prerequisite(s) {missing} not yet "
                    "seen - the model didn't list milestones in dependency order"
                )
            milestone = create_milestone(
                name=generated.name,
                description=generated.description,
                cefr_level=generated.cefr_level,
                prerequisite_ids=[key_to_id[key] for key in generated.prerequisite_keys],
            )
            key_to_id[generated.key] = milestone.id
            print(f"  [{milestone.id}] {milestone.cefr_level} {milestone.name} - {milestone.description}")
    except Exception:
        log.exception("failed to generate milestones")
        print("Failed to generate milestones - see logs/contxt.log", file=sys.stderr)
        return 1

    print(f"Created {len(key_to_id)} milestones. Skim the sequence above and its prerequisite structure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
