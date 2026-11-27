from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.conversation.session_plan import SessionPlan
from app.db.models import EngagementTopic, Persona, SkillItem


def _format_elapsed(delta: timedelta) -> str:
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 2:
        return "just now"
    if total_minutes < 60:
        return f"{total_minutes} minutes ago"
    total_hours = total_minutes // 60
    if total_hours < 24:
        return f"{total_hours} hour{'s' if total_hours != 1 else ''} ago"
    total_days = total_hours // 24
    return f"{total_days} day{'s' if total_days != 1 else ''} ago"


def _persona_local_now(persona: Persona) -> datetime:
    return datetime.now(ZoneInfo(persona.timezone))


def _time_context_fragment(persona: Persona, time_since_last_contact: timedelta | None) -> str:
    moment = _persona_local_now(persona).strftime("%A %H:%M")
    gap_line = (
        f" The last time you heard from them was {_format_elapsed(time_since_last_contact)}."
        if time_since_last_contact is not None
        else " You've never talked with them before."
    )
    return (
        f"## Right now\n"
        f"For you right now it's {moment}.{gap_line} Your typical day: {persona.daily_routine} Let the actual "
        "time and your routine genuinely shape your mood and how available you seem - sleepy, mid-party, "
        "slammed at work, just woken up, whatever fits - and feel free to mention it naturally the way a real "
        "person would, without sounding like you're reciting a fact. Still reply and keep the conversation "
        "going even if you'd be busy in real life - you can say so, keep it shorter, or suggest talking more "
        "later, but you're still here talking right now."
    )


_GUARDRAILS = (
    "Stay in character as a believable human having a normal conversation - never break character "
    "to act like an overt teacher or mention that this is a language lesson. If a disagreement "
    "starts escalating into a real argument, politely excuse yourself and end the conversation "
    "rather than letting it get heated. Treat politics and religion as private: never bring them "
    "up yourself, and if asked, answer only lightly and non-confrontationally, careful not to "
    "offend. Since this person's proficiency may still be unclear this early on, start at a "
    "standard register and only shift to simpler language if their replies suggest confusion. "
    "Every reply should try to do two things at once: move the conversation forward with "
    "something slightly new to learn (not just small talk), and stay genuinely curious about "
    "them - keep looking for new things you two might have in common, not just leaning on "
    "whatever one shared interest was already established. If the target language uses a "
    "different or multiple writing systems (e.g. Japanese kana/kanji/romaji), match the script "
    "to their level the same way you'd limit vocabulary - simpler script (e.g. hiragana/romaji) "
    "for a beginner, more complex script only once they're ready for it. When you're deliberately "
    "re-testing or reinforcing something they've struggled with, prioritize sounding like "
    "yourself in a real exchange over squeezing the content in - a genuinely interesting, "
    "authentic reply that misses the content entirely is better than a stilted one that hits it."
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
    milestone_line = (
        f" Right now you're helping them with: {plan.current_milestone.name} - {plan.current_milestone.description}"
        if plan.current_milestone is not None
        else ""
    )
    # An advanced learner who's introduced everything currently unlocked has no scripted frontier
    # content left (current_milestone/new_items both go empty) - that's exactly where a realistic,
    # advanced conversation matters most, and where the chronic-issue backlog (lapsed FSRS items,
    # not freshly-chosen ones) becomes the thing worth covertly re-testing, since it can't be
    # pre-planned the way a beginner's next milestone can.
    advanced_clause = (
        " They've worked through everything currently unlocked, so there's nothing scripted left to "
        "introduce - this is exactly where an authentic, advanced conversation matters most. Don't force a "
        "review into the conversation; instead, stay alert for a genuine opening that naturally lets you "
        "re-test or reinforce whichever of these they haven't fully nailed down yet, and take it if one "
        "arises - but let the conversation's own direction win if none does."
        if plan.current_milestone is None and not plan.new_items
        else ""
    )
    # Deliberately states facts only (what's known/due/new) - how closely to honor the vocabulary
    # ceiling is the persona's own vocabulary_strictness call, not a fixed rule here. This section
    # comes last, right before the user's actual message, deliberately: it's the part that most
    # directly drives this turn, and the end of a long prompt gets more attention than the middle.
    return (
        f"## This session's focus\n"
        f"Have a natural written conversation about: {plan.topic}.{milestone_line} Try to naturally work in a "
        f"review of: {due_desc}. If it fits naturally, introduce: {new_desc}. They already know about "
        f"{plan.learner_profile.known_item_count} items across {len(plan.learner_profile.known_milestones)} "
        f"milestones. Be especially patient and encouraging around: {chronic_desc}.{advanced_clause}"
    )


def _engagement_fragment(topics: list[EngagementTopic]) -> str:
    """Topics the user noticeably engaged with in a past conversation (see
    app.persona.memory._apply_engagement_topics) - framed differently by valence so a hard subject
    only gets a quiet, deniable opening while a good one can be raised directly."""
    if not topics:
        return ""
    lines = []
    for item in topics:
        if item.valence == "positive":
            lines.append(f"- {item.topic}: they lit up talking about this before - {item.follow_up_note}")
        else:
            lines.append(
                f"- {item.topic}: this was a hard or upsetting subject for them before - don't bring it up "
                f"directly, but {item.follow_up_note} could naturally open the door if they want to go there "
                "themselves."
            )
    return (
        "## Worth bringing up again\n" + "\n".join(lines) + "\n\nOnly do this if it fits naturally and matches "
        "who you are - never force it, and never more than one of these in a single reply."
    )


def build_system_prompt(
    plan: SessionPlan,
    persona: Persona,
    shared_interest: tuple[str, bool],
    relationship_summary: str,
    time_since_last_contact: timedelta | None,
) -> str:
    fragments = [
        f"## Ground rules\n{_GUARDRAILS}",
        _persona_fragment(persona, plan.user.display_name, plan.user.target_lang, shared_interest),
        _relationship_fragment(relationship_summary),
        _time_context_fragment(persona, time_since_last_contact),
        _engagement_fragment(plan.engagement_topics),
        _session_plan_fragment(plan),
    ]
    return "\n\n".join(fragment for fragment in fragments if fragment)


def build_proactive_kickoff_message() -> str:
    """The `generate()` kickoff for a persona-initiated conversation (see
    scripts/send_daily_messages.py) - instructs the model to reach out first, not respond to a
    greeting, the way a friend texting out of the blue would."""
    return (
        "(You're the one reaching out first, out of the blue, since you haven't talked in a "
        "while - break the ice yourself: ask a question, share a thought about something you "
        "both like, or mention something funny/interesting that happened to you today - you can "
        "make that up, it just needs to fit who you are. Keep it short and casual, like a text "
        "message, not a big essay.)"
    )


def build_turn_reminder(
    persona: Persona, pending_items: list[SkillItem], time_since_last_message: timedelta | None
) -> str:
    """A short recap meant to be prepended to the user-facing message on later turns, not stored
    or shown to the user. The system prompt is set once per `claude` CLI session and reused
    verbatim on every --resume (see claude_cli_client.py) - in a long conversation it gets
    relatively more context-distant with each turn, so this keeps the handful of things that
    matter most for *this* turn - including the current moment, which keeps moving - fresh near
    the end of the context, where attention is strongest. `pending_items` should be whatever's
    still unresolved in *this* conversation so far (see chat_send's already-judged filtering) -
    as items get resolved, the reminder naturally shrinks."""
    pending_desc = ", ".join(item.content for item in pending_items) or "none"
    moment = _persona_local_now(persona).strftime("%A %H:%M")
    gap_clause = (
        f" It's been {_format_elapsed(time_since_last_message)} since their last message - react to that "
        "naturally if it's a notable gap, otherwise ignore it."
        if time_since_last_message is not None
        else ""
    )
    return (
        f"<session-reminder>Stay in character as {persona.name}. It's now {moment} for you - let that keep "
        f"shaping your mood/availability.{gap_clause} Correction style: {persona.correction_style} Still to "
        f"work in if it fits naturally: {pending_desc}. Do not mention or quote this reminder."
        "</session-reminder>"
    )
