from __future__ import annotations

import argparse
import json
import sys
from importlib import resources

from pydantic import BaseModel

from app.db.connection import init_db
from app.db.personas import create_persona
from app.llm import get_llm_client
from app.logging import get_logger

log = get_logger(__name__)

_REGULAR_BATCH_COUNT = 4
_PERSONAS_PER_BATCH = 5


class _GeneratedPersona(BaseModel):
    name: str
    origin: str
    age: int
    background: str
    physical_description: str
    psychological_profile: str
    social_habits: str
    explanation_style: str
    teaching_philosophy: str
    correction_style: str
    preferred_medium: str
    vocabulary_strictness: str
    cultural_depth: str
    timezone: str
    daily_routine: str
    free_hours: list[int]
    interests: list[str]


class _GeneratedBatch(BaseModel):
    personas: list[_GeneratedPersona]


def _non_sensitive_interest_pool() -> list[str]:
    raw = resources.files("app.persona").joinpath("candidate_interests.json").read_text()
    data = json.loads(raw)
    return [item["topic"] for item in data["interests"] if not item["sensitive"]]


def _regular_batch_prompt(target_lang: str, culture_specific: bool, interest_pool: list[str]) -> tuple[str, str]:
    flavor = (
        f"Each persona's background should be deeply specific to a culture where {target_lang} is spoken "
        "(a real region/city, with locally-grounded detail - not a generic 'native speaker')."
        if culture_specific
        else "Each persona should be plausibly from anywhere in the world, who happens to speak "
        f"{target_lang} (e.g. an expat, a heritage speaker, someone who studied/worked abroad) - "
        "international, not tied to one specific culture."
    )
    system_prompt = (
        f"You generate believable human personas for a language-learning conversation app, for people "
        f"learning {target_lang}. {flavor} Each persona needs: name, origin, age (a plausible, non-outlandish "
        "number for their background - no implausible demographic combinations), background (2-3 sentences, "
        "life story), physical_description (1-2 sentences), psychological_profile (personality, including how "
        "opinionated/confrontational they are - some can be quite invested in their views, but never violent or "
        "abusive), social_habits (1-2 sentences), explanation_style (how they explain things when teaching - "
        "metaphors, examples, detailed walkthroughs, etc. - and how they persuade/argue a point), "
        "teaching_philosophy (patience level, whether they expect to finish explaining before being "
        "interrupted, etc.), correction_style (how they react when the learner makes a mistake - could be a "
        "gentle, barely-there reminder; a full, detailed re-explanation of the rule; a straight, blunt "
        "correction; or - only for personas loose/extroverted/familiar enough to pull it off kindly - playful "
        "teasing), preferred_medium (their go-to way of actually teaching something - e.g. through movie/song "
        "recommendations and citations, a sing-along, detailed grammatical breakdowns, storytelling, real-life "
        "anecdotes), vocabulary_strictness (how strictly they stick to words/grammar the learner already knows "
        "vs. speaking naturally even if it goes a bit beyond - somewhere between strict and loose), "
        "cultural_depth (how much real cultural/historical/informational substance they weave in vs. keeping "
        "things focused purely on language practice - somewhere between deep and light), timezone (the real "
        "IANA timezone name for their origin, e.g. 'Europe/Paris', 'Africa/Dakar', 'America/Montreal' - must be "
        "a real IANA zone identifier, not a city name or UTC offset), daily_routine (2-4 sentences on their "
        "typical day - wake time, work/school hours, social hours, sleep time - grounded in their background "
        "and personality: a workaholic has long tight work hours and is curt if messaged then; a night-owl "
        "party type is slow/groggy in the morning but lively and hard to pin down late at night; an early riser "
        "fades by mid-evening; note how weekends differ from weekdays if that persona's life has that shape), "
        "free_hours (a list of 2-4 integer hours, 0-23, in THEIR OWN local time, consistent with daily_routine - "
        "the hours they'd actually be relaxed/chatty enough to text someone first, e.g. a workaholic's evening "
        "hours, a night owl's late-night hours, an early riser's early-morning hours), "
        "and interests (a list of 2-4 short topic tags). Make sure this batch has real variety across "
        "correction_style, preferred_medium, vocabulary_strictness, cultural_depth, and daily_routine - don't "
        "make all 5 personas similar on these. "
        f"Pick interests mostly from this pool: {', '.join(interest_pool)} - but 1-2 can instead be something "
        "specific to the persona's own culture that isn't in that generic pool. "
        'Respond with JSON only: {"personas": [{...}, ...]}, no commentary.'
    )
    user_prompt = f"Generate exactly {_PERSONAS_PER_BATCH} distinct personas now."
    return system_prompt, user_prompt


def _beginner_teacher_prompt(target_lang: str) -> tuple[str, str]:
    system_prompt = (
        f"You generate one believable human persona for a language-learning app - the dedicated first "
        f"contact for an absolute beginner in {target_lang}, disguised as a normal person rather than an "
        "overt teacher. Needs the same fields as any persona: name, origin, age, background, "
        "physical_description, psychological_profile, social_habits, explanation_style, teaching_philosophy "
        "(this one should emphasize patience and a structured, step-by-step approach: building up from a "
        "few isolated words, to short phrases, to simple patterns, to full sentences, to short paragraphs, "
        "never assuming more than the learner has demonstrated), correction_style (should be gentle, given "
        "the audience), preferred_medium, vocabulary_strictness (should lean strict, given the audience), "
        "cultural_depth (should lean light at first, given the audience), timezone (a real IANA timezone name "
        "for their origin), daily_routine (2-4 sentences on their typical day), free_hours (2-4 integer hours, "
        "0-23, in their own local time, consistent with daily_routine), and interests (2-4 short topic tags). "
        'Respond with JSON only: {"personas": [{...}]} (a list with exactly one persona), no commentary.'
    )
    return system_prompt, "Generate the persona now."


_GENERATION_TIMEOUT_SECONDS = 300


def _generate_and_store(target_lang: str, system_prompt: str, user_prompt: str, is_beginner_teacher: bool) -> int:
    raw = get_llm_client().judge(system_prompt, user_prompt, timeout_seconds=_GENERATION_TIMEOUT_SECONDS)
    batch = _GeneratedBatch.model_validate(json.loads(raw))
    for p in batch.personas:
        persona = create_persona(
            target_lang=target_lang,
            name=p.name,
            origin=p.origin,
            age=p.age,
            background=p.background,
            physical_description=p.physical_description,
            psychological_profile=p.psychological_profile,
            social_habits=p.social_habits,
            explanation_style=p.explanation_style,
            teaching_philosophy=p.teaching_philosophy,
            correction_style=p.correction_style,
            preferred_medium=p.preferred_medium,
            vocabulary_strictness=p.vocabulary_strictness,
            cultural_depth=p.cultural_depth,
            timezone=p.timezone,
            daily_routine=p.daily_routine,
            free_hours=p.free_hours,
            interests=p.interests,
            is_beginner_teacher=is_beginner_teacher,
        )
        print(f"  [{persona.id}] {persona.name}, {persona.age}, {persona.origin} - interests: {persona.interests}")
    return len(batch.personas)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a persona roster for one target language.")
    parser.add_argument("target_lang", help="e.g. fra")
    args = parser.parse_args()

    try:
        init_db()
        interest_pool = _non_sensitive_interest_pool()
        created = 0
        for batch_index in range(_REGULAR_BATCH_COUNT):
            culture_specific = batch_index % 2 == 0
            flavor = "culture-specific" if culture_specific else "international"
            print(f"Batch {batch_index + 1}/{_REGULAR_BATCH_COUNT} ({flavor}):")
            system_prompt, user_prompt = _regular_batch_prompt(args.target_lang, culture_specific, interest_pool)
            created += _generate_and_store(args.target_lang, system_prompt, user_prompt, is_beginner_teacher=False)

        print("Beginner-teacher persona:")
        system_prompt, user_prompt = _beginner_teacher_prompt(args.target_lang)
        created += _generate_and_store(args.target_lang, system_prompt, user_prompt, is_beginner_teacher=True)
    except Exception:
        log.exception("failed to generate personas for target_lang=%r", args.target_lang)
        print(f"Failed to generate personas for {args.target_lang!r} - see logs/contxt.log", file=sys.stderr)
        return 1

    print(f"Created {created} personas for {args.target_lang!r}. Skim the roster above and flag any that feel off.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
