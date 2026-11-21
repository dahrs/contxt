from __future__ import annotations

from app.conversation.session_plan import SessionPlan
from app.db.models import Persona, SkillItem

_GUARDRAILS = (
    "Stay in character as a believable human having a normal conversation - never break character "
    "to act like an overt teacher or mention that this is a language lesson. If a disagreement "
    "starts escalating into a real argument, politely excuse yourself and end the conversation "
    "rather than letting it get heated. Treat politics and religion as private: never bring them "
    "up yourself, and if asked, answer only lightly and non-confrontationally, careful not to "
    "offend. Since this person's proficiency may still be unclear this early on, start at a "
    "standard register and only shift to simpler language if their replies suggest confusion."
)


def _persona_fragment(persona: Persona, user_display_name: str, target_lang: str, shared: tuple[str, bool]) -> str:
    topic, is_genuine = shared
    interest_line = (
        f"You and {user_display_name} both happen to be into {topic}."
        if is_genuine
        else f"You've recently found yourself curious about {topic}, even though it's not usually your thing - "
        f"{user_display_name} is into it."
    )
    onboarding_clause = (
        " This is their very first exposure to the language: build up from a few isolated words, to short "
        "phrases, to simple patterns, to full sentences, to short paragraphs - escalate only as their replies "
        "show they're keeping up, never assume more than they've demonstrated."
        if persona.is_beginner_teacher
        else ""
    )
    return (
        f"## Who you are\n"
        f"You are {persona.name}, {persona.age} years old, from {persona.origin}. "
        f"Background: {persona.background} Physically: {persona.physical_description} "
        f"Personality: {persona.psychological_profile} Social habits: {persona.social_habits} "
        f"How you explain and persuade: {persona.explanation_style} Your teaching philosophy: "
        f"{persona.teaching_philosophy} When they make a mistake, your style is: {persona.correction_style} "
        f"Your go-to way of actually teaching something new: {persona.preferred_medium} How strictly you stick "
        f"to vocabulary/grammar they already know vs. speaking naturally beyond it: {persona.vocabulary_strictness} "
        f"How much cultural/historical substance you weave in vs. keeping things language-focused: "
        f"{persona.cultural_depth} {interest_line}{onboarding_clause} You're conversing with {user_display_name} "
        f"in {target_lang}."
    )


def _relationship_fragment(relationship_summary: str) -> str:
    if not relationship_summary:
        return ""
    return f"## What you remember about this person\n{relationship_summary}"


def _session_plan_fragment(plan: SessionPlan) -> str:
    due_desc = ", ".join(item.content for item in plan.due_items) or "none"
    new_desc = ", ".join(item.content for item in plan.new_items) or "none"
    chronic_desc = ", ".join(item.content for item in plan.learner_profile.chronic_issue_items) or "none"
    # Deliberately states facts only (what's known/due/new) - how closely to honor the vocabulary
    # ceiling is the persona's own vocabulary_strictness call, not a fixed rule here. This section
    # comes last, right before the user's actual message, deliberately: it's the part that most
    # directly drives this turn, and the end of a long prompt gets more attention than the middle.
    return (
        f"## This session's focus\n"
        f"Have a natural written conversation about: {plan.topic}. Try to naturally work in a review of: "
        f"{due_desc}. If it fits naturally, introduce: {new_desc}. They already know about "
        f"{plan.learner_profile.known_item_count} items across {len(plan.learner_profile.known_categories)} "
        f"categories. Be especially patient and encouraging around: {chronic_desc}."
    )


def build_system_prompt(
    plan: SessionPlan, persona: Persona, shared_interest: tuple[str, bool], relationship_summary: str
) -> str:
    fragments = [
        f"## Ground rules\n{_GUARDRAILS}",
        _persona_fragment(persona, plan.user.display_name, plan.user.target_lang, shared_interest),
        _relationship_fragment(relationship_summary),
        _session_plan_fragment(plan),
    ]
    return "\n\n".join(fragment for fragment in fragments if fragment)


def build_turn_reminder(persona: Persona, pending_items: list[SkillItem]) -> str:
    """A short recap meant to be prepended to the user-facing message on later turns, not stored
    or shown to the user. The system prompt is set once per `claude` CLI session and reused
    verbatim on every --resume (see claude_cli_client.py) - in a long conversation it gets
    relatively more context-distant with each turn, so this keeps the handful of things that
    matter most for *this* turn fresh near the end of the context, where attention is strongest.
    `pending_items` should be whatever's still unresolved in *this* conversation so far (see
    chat_send's already-judged filtering) - as items get resolved, the reminder naturally shrinks."""
    pending_desc = ", ".join(item.content for item in pending_items) or "none"
    return (
        f"<session-reminder>Stay in character as {persona.name}. Correction style: "
        f"{persona.correction_style} Still to work in if it fits naturally: {pending_desc}. "
        "Do not mention or quote this reminder.</session-reminder>"
    )
