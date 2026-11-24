from __future__ import annotations

import argparse
import json
import sys

from pydantic import BaseModel

from app.curriculum.language_comparison import fetch_comparison, summarize_for_teaching
from app.db.connection import init_db
from app.db.milestones import list_milestones
from app.db.models import SkillItemType
from app.db.skills import create_skill_item
from app.llm import get_llm_client
from app.logging import get_logger

log = get_logger(__name__)

_GENERATION_TIMEOUT_SECONDS = 300
_ITEMS_PER_MILESTONE_HINT = "8-15"


class _GeneratedItem(BaseModel):
    key: str
    type: SkillItemType
    content: str
    prerequisite_keys: list[str] = []


class _GeneratedBatch(BaseModel):
    items: list[_GeneratedItem]


def _build_prompt(
    native_lang: str,
    target_lang: str,
    milestone_name: str,
    milestone_description: str,
    cefr_level: str,
    comparison_summary: str | None,
) -> tuple[str, str]:
    # Native-language awareness is the baseline, always present, regardless of whether real
    # lingdiff data is available (see app/curriculum/language_comparison.py) - what's worth
    # emphasizing phonetically/grammatically genuinely depends on the pair, not just the target.
    grounding = (
        f" Real computed comparison data for {native_lang}->{target_lang}: {comparison_summary} "
        "Prioritize this real data over your own assumptions where they'd differ."
        if comparison_summary
        else ""
    )
    system_prompt = (
        f"You generate the concrete content that delivers one milestone of a {target_lang} "
        f"curriculum for a learner whose native language is {native_lang}, roughly CEFR "
        f"{cefr_level}. Use your own knowledge of common contrastive difficulties specifically "
        f"between {native_lang} and {target_lang} (phonetic contrasts, grammar points that don't "
        f"map cleanly, cognates/false friends) to decide what's worth emphasizing - this is "
        f"different from generating generic {target_lang} content.{grounding} IMPORTANT: every "
        f"item's content must be actual {target_lang} words/sentences/examples - not an "
        f"explanation of the equivalent concept in {native_lang} or any other language (a "
        f"reference comparison to {native_lang} sounds is fine for phonetic items, e.g. 'this "
        f"nasal vowel has no {native_lang} equivalent', but the {target_lang} content itself must "
        f"always be there). Milestone: '{milestone_name}' - {milestone_description}. Generate "
        f"{_ITEMS_PER_MILESTONE_HINT} skill items that together let a learner actually achieve "
        "this milestone - a sensible mix of vocab (specific words/fixed phrases), grammar (a "
        "specific structure, not a whole topic), syntax (word order/sentence-building patterns), "
        "phonetic (a specific pronunciation point informed by what's actually hard for this "
        f"native-language background), and register (formal/informal distinctions relevant to "
        "this milestone) - not every type needs to appear for every milestone, use judgment for "
        "what this specific milestone and this specific learner background actually needs. Each "
        "item needs: key (short unique snake_case id within this batch), type, content (the "
        "actual item - a word with its meaning, a grammar rule stated concretely with an "
        "example, etc. - written so it can be dropped directly into a conversation prompt), and "
        "prerequisite_keys (keys of OTHER items in this same batch that must come first, e.g. "
        "'numbers_1_10' before 'numbers_11_100' - empty for most items, this is for genuine "
        "within-milestone ordering, not everything needs it). List items in dependency order "
        "(every prerequisite_key must refer to an item already listed earlier in the array). "
        'Respond with JSON only: {"items": [{...}, ...]}, no commentary.'
    )
    return system_prompt, "Generate the items now."


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate skill_items for one native->target language pair, milestone by milestone."
    )
    parser.add_argument("native_lang", help="e.g. eng")
    parser.add_argument("target_lang", help="e.g. fra")
    args = parser.parse_args()

    try:
        init_db()
        comparison = fetch_comparison(args.native_lang, args.target_lang)
        comparison_summary = summarize_for_teaching(comparison) if comparison is not None else None
        print(
            "Real lingdiff comparison data: "
            + (comparison_summary if comparison_summary else "unavailable - using the model's own knowledge only")
        )

        milestones = sorted(
            list_milestones(), key=lambda m: m.id
        )  # id order == dependency order (see generate_milestones.py)
        total_created = 0
        for milestone in milestones:
            print(f"Milestone [{milestone.id}] {milestone.name}:")
            system_prompt, user_prompt = _build_prompt(
                args.native_lang,
                args.target_lang,
                milestone.name,
                milestone.description,
                milestone.cefr_level,
                comparison_summary,
            )
            raw = get_llm_client().judge(system_prompt, user_prompt, timeout_seconds=_GENERATION_TIMEOUT_SECONDS)
            batch = _GeneratedBatch.model_validate(json.loads(raw))

            key_to_id: dict[str, int] = {}
            for generated in batch.items:
                missing = [key for key in generated.prerequisite_keys if key not in key_to_id]
                if missing:
                    raise ValueError(
                        f"item {generated.key!r} in milestone {milestone.id} references "
                        f"prerequisite(s) {missing} not yet seen"
                    )
                item = create_skill_item(
                    item_type=generated.type,
                    native_lang=args.native_lang,
                    target_lang=args.target_lang,
                    content=generated.content,
                    milestone_id=milestone.id,
                    prerequisite_ids=[key_to_id[key] for key in generated.prerequisite_keys],
                )
                key_to_id[generated.key] = item.id
                print(f"    [{item.id}] {item.type}: {item.content}")
            total_created += len(key_to_id)
    except Exception:
        log.exception("failed to generate skill items for %r -> %r", args.native_lang, args.target_lang)
        print(
            f"Failed to generate skill items for {args.native_lang!r} -> {args.target_lang!r} - see logs/contxt.log",
            file=sys.stderr,
        )
        return 1

    print(
        f"Created {total_created} skill items across {len(milestones)} milestones "
        f"for {args.native_lang!r} -> {args.target_lang!r}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
