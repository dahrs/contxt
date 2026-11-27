from __future__ import annotations

from datetime import timedelta

from app.conversation.prompt import build_proactive_kickoff_message, build_system_prompt, build_turn_reminder
from app.conversation.session_plan import LearnerProfileSummary, SessionPlan
from app.db.models import EngagementTopic, Milestone, Persona, SkillItem, User


def _user() -> User:
    return User(
        id=1,
        username="alice",
        password_hash="x",
        display_name="Alice",
        native_lang="eng",
        target_lang="fra",
        is_absolute_beginner=False,
        email=None,
        last_proactive_sent_at=None,
        created_at="2026-01-01T00:00:00Z",
    )


def _item(id_: int, content: str) -> SkillItem:
    return SkillItem(
        id=id_, type="vocab", native_lang="eng", target_lang="fra", content=content, milestone_id=1, prerequisite_ids=[]
    )


def _plan(**overrides: object) -> SessionPlan:
    defaults: dict[str, object] = {
        "user": _user(),
        "topic": "travel",
        "due_items": [_item(1, "bonjour")],
        "new_items": [_item(2, "au revoir")],
        "current_milestone": None,
        "learner_profile": LearnerProfileSummary(
            known_item_count=5, known_milestones={"greetings": 5}, chronic_issue_items=[]
        ),
        "engagement_topics": [],
    }
    defaults.update(overrides)
    return SessionPlan.model_validate(defaults)


def _engagement_topic(
    topic: str = "half-marathon training", valence: str = "positive", note: str = "ask how it went"
) -> EngagementTopic:
    return EngagementTopic(
        id=1, user_id=1, topic=topic, valence=valence, follow_up_note=note, surfaced_at=None, created_at="x"
    )


def _persona(**overrides: object) -> Persona:
    defaults: dict[str, object] = {
        "id": 1,
        "target_lang": "fra",
        "name": "Camille",
        "origin": "Tours",
        "age": 34,
        "background": "bg",
        "physical_description": "desc",
        "psychological_profile": "warm",
        "social_habits": "habits",
        "explanation_style": "metaphors",
        "teaching_philosophy": "patient",
        "correction_style": "gentle",
        "preferred_medium": "storytelling",
        "vocabulary_strictness": "strict",
        "cultural_depth": "light",
        "timezone": "UTC",
        "daily_routine": "N/A",
        "free_hours": list(range(24)),
        "is_beginner_teacher": False,
        "interests": ["cooking"],
    }
    defaults.update(overrides)
    return Persona.model_validate(defaults)


def test__build_system_prompt_includes_guardrails_and_persona_voice() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "", None)

    assert "excuse yourself" in prompt
    assert "Camille" in prompt
    assert "metaphors" in prompt
    assert "gentle" in prompt


def test__build_system_prompt_does_not_hardcode_vocabulary_strictness() -> None:
    """Regression test: the session-plan fragment used to hardcode 'stay within vocabulary
    they'd plausibly know' for every persona, which fought a loose persona's own strictness
    setting. That line should be gone - strictness comes only from the persona field."""
    prompt = build_system_prompt(_plan(), _persona(vocabulary_strictness="loose"), ("cooking", True), "", None)

    assert "stay within vocabulary" not in prompt
    assert "loose" in prompt


def test__build_system_prompt_genuine_shared_interest_framing() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "", None)

    assert "both happen to be into cooking" in prompt


def test__build_system_prompt_fallback_shared_interest_framing() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("chess", False), "", None)

    assert "recently found yourself curious about chess" in prompt


def test__build_system_prompt_omits_relationship_fragment_when_empty() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "", None)

    assert "What you remember about this person" not in prompt


def test__build_system_prompt_includes_relationship_fragment_when_present() -> None:
    prompt = build_system_prompt(
        _plan(), _persona(), ("cooking", True), "she is a software engineer who runs trails", None
    )

    assert "she is a software engineer who runs trails" in prompt


def test__build_system_prompt_includes_onboarding_clause_only_for_beginner_teacher() -> None:
    regular = build_system_prompt(_plan(), _persona(is_beginner_teacher=False), ("cooking", True), "", None)
    teacher = build_system_prompt(_plan(), _persona(is_beginner_teacher=True), ("cooking", True), "", None)

    assert "very first exposure" not in regular
    assert "very first exposure" in teacher


def test__build_system_prompt_includes_session_plan_facts() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "", None)

    assert "bonjour" in prompt
    assert "au revoir" in prompt
    assert "travel" in prompt


def test__build_system_prompt_sections_are_labeled_and_session_focus_comes_last() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "remembered fact", None)

    sections = [
        "## Ground rules",
        "## Who you are",
        "## What you remember about this person",
        "## Right now",
        "## This session's focus",
    ]
    positions = [prompt.index(s) for s in sections]
    assert positions == sorted(positions)  # each section appears, in that order
    assert positions[-1] == max(positions)  # session focus is the last section, closest to the user's turn


def test__build_system_prompt_mentions_never_met_before_when_no_prior_contact() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "", None)

    assert "never talked with them before" in prompt


def test__build_system_prompt_mentions_elapsed_time_since_last_contact() -> None:

    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "", timedelta(days=3))

    assert "3 days ago" in prompt


def test__build_system_prompt_includes_daily_routine() -> None:
    persona = _persona(daily_routine="wakes at dawn, sleeps by 9pm")
    prompt = build_system_prompt(_plan(), persona, ("cooking", True), "", None)

    assert "wakes at dawn, sleeps by 9pm" in prompt


def test__build_turn_reminder_names_persona_and_correction_style() -> None:
    reminder = build_turn_reminder(
        _persona(name="Camille", correction_style="gentle"), pending_items=[], time_since_last_message=None
    )

    assert "Camille" in reminder
    assert "gentle" in reminder
    assert "none" in reminder  # no pending items


def test__build_turn_reminder_lists_still_pending_items() -> None:
    reminder = build_turn_reminder(_persona(), pending_items=[_item(1, "bonjour")], time_since_last_message=None)

    assert "bonjour" in reminder


def test__build_turn_reminder_mentions_gap_when_time_has_passed() -> None:

    reminder = build_turn_reminder(_persona(), pending_items=[], time_since_last_message=timedelta(hours=2))

    assert "2 hours ago" in reminder


def test__build_turn_reminder_omits_gap_clause_within_the_same_exchange() -> None:
    reminder = build_turn_reminder(_persona(), pending_items=[], time_since_last_message=None)

    assert "since their last message" not in reminder


def test__build_proactive_kickoff_message_instructs_breaking_the_ice() -> None:
    message = build_proactive_kickoff_message()

    assert "reaching out first" in message
    assert "break the ice" in message


def test__build_system_prompt_dual_motivation_and_script_matching_in_guardrails() -> None:
    prompt = build_system_prompt(_plan(), _persona(), ("cooking", True), "", None)

    assert "something slightly new to learn" in prompt
    assert "match the script to their level" in prompt


def test__build_system_prompt_mentions_current_milestone_when_set() -> None:
    milestone = Milestone(id=1, name="Greetings", description="Can greet someone", cefr_level="A1", prerequisite_ids=[])

    prompt = build_system_prompt(_plan(current_milestone=milestone), _persona(), ("cooking", True), "", None)

    assert "Greetings" in prompt
    assert "Can greet someone" in prompt


def test__build_system_prompt_omits_milestone_line_when_none() -> None:
    prompt = build_system_prompt(_plan(current_milestone=None), _persona(), ("cooking", True), "", None)

    assert "helping them with" not in prompt


def test__build_system_prompt_includes_advanced_clause_when_frontier_exhausted() -> None:
    prompt = build_system_prompt(_plan(current_milestone=None, new_items=[]), _persona(), ("cooking", True), "", None)

    assert "nothing scripted left to introduce" in prompt


def test__build_system_prompt_omits_advanced_clause_when_new_items_remain() -> None:
    prompt = build_system_prompt(_plan(current_milestone=None), _persona(), ("cooking", True), "", None)

    assert "nothing scripted left to introduce" not in prompt


def test__build_system_prompt_omits_advanced_clause_when_milestone_in_progress() -> None:
    milestone = Milestone(id=1, name="Greetings", description="Can greet someone", cefr_level="A1", prerequisite_ids=[])
    prompt = build_system_prompt(
        _plan(current_milestone=milestone, new_items=[]), _persona(), ("cooking", True), "", None
    )

    assert "nothing scripted left to introduce" not in prompt


def test__build_system_prompt_omits_engagement_fragment_when_no_topics() -> None:
    prompt = build_system_prompt(_plan(engagement_topics=[]), _persona(), ("cooking", True), "", None)

    assert "Worth bringing up again" not in prompt


def test__build_system_prompt_positive_engagement_topic_invites_a_direct_follow_up() -> None:
    topic = _engagement_topic(valence="positive", note="ask how the race went")
    prompt = build_system_prompt(_plan(engagement_topics=[topic]), _persona(), ("cooking", True), "", None)

    assert "Worth bringing up again" in prompt
    assert "half-marathon training" in prompt
    assert "ask how the race went" in prompt
    assert "don't bring it up directly" not in prompt


def test__build_system_prompt_negative_engagement_topic_only_suggests_an_oblique_opening() -> None:
    topic = _engagement_topic(valence="negative", note="ask how work has been lately")
    prompt = build_system_prompt(_plan(engagement_topics=[topic]), _persona(), ("cooking", True), "", None)

    assert "don't bring it up directly" in prompt
    assert "ask how work has been lately" in prompt


def test__build_system_prompt_session_focus_still_comes_last_with_engagement_topics_present() -> None:
    topic = _engagement_topic()
    prompt = build_system_prompt(_plan(engagement_topics=[topic]), _persona(), ("cooking", True), "", None)

    assert prompt.index("Worth bringing up again") < prompt.index("This session's focus")
