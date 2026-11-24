from __future__ import annotations

import json

from app.conversation.authenticity import verify_and_rephrase
from app.db.models import Persona, SkillItem
from test.conftest import FakeLLMClient


def _persona() -> Persona:
    return Persona(
        id=1,
        target_lang="fra",
        name="Camille",
        origin="N/A",
        age=30,
        background="N/A",
        physical_description="N/A",
        psychological_profile="N/A",
        social_habits="N/A",
        explanation_style="N/A",
        teaching_philosophy="N/A",
        correction_style="N/A",
        preferred_medium="N/A",
        vocabulary_strictness="N/A",
        cultural_depth="N/A",
        timezone="UTC",
        daily_routine="N/A",
        free_hours=list(range(24)),
        is_beginner_teacher=False,
        interests=[],
    )


def _item(id_: int, content: str) -> SkillItem:
    return SkillItem(
        id=id_, type="vocab", native_lang="eng", target_lang="fra", content=content, milestone_id=1, prerequisite_ids=[]
    )


def test__verify_and_rephrase_skips_llm_call_when_no_focus_items(fake_llm: FakeLLMClient) -> None:
    result = verify_and_rephrase(fake_llm, _persona(), "a normal reply", focus_items=[])

    assert result == "a normal reply"
    assert fake_llm.judge_calls == []


def test__verify_and_rephrase_returns_draft_unchanged_when_already_authentic(fake_llm: FakeLLMClient) -> None:
    fake_llm.judge_response = json.dumps({"is_authentic": True, "rewritten_reply": "a natural reply"})

    result = verify_and_rephrase(fake_llm, _persona(), "a natural reply", focus_items=[_item(1, "bonjour")])

    assert result == "a natural reply"
    assert len(fake_llm.judge_calls) == 1


def test__verify_and_rephrase_returns_rewrite_when_flagged_inauthentic(fake_llm: FakeLLMClient) -> None:
    fake_llm.judge_response = json.dumps({"is_authentic": False, "rewritten_reply": "a less didactic reply"})

    result = verify_and_rephrase(
        fake_llm, _persona(), "Today's lesson is about bonjour!", focus_items=[_item(1, "bonjour")]
    )

    assert result == "a less didactic reply"


def test__verify_and_rephrase_falls_back_to_draft_on_unparseable_output(fake_llm: FakeLLMClient) -> None:
    fake_llm.judge_response = "not json"

    result = verify_and_rephrase(fake_llm, _persona(), "a normal reply", focus_items=[_item(1, "bonjour")])

    assert result == "a normal reply"


def test__verify_and_rephrase_falls_back_to_draft_on_missing_fields(fake_llm: FakeLLMClient) -> None:
    fake_llm.judge_response = json.dumps({"outcomes": []})  # wrong shape entirely

    result = verify_and_rephrase(fake_llm, _persona(), "a normal reply", focus_items=[_item(1, "bonjour")])

    assert result == "a normal reply"


def test__verify_and_rephrase_includes_persona_name_and_focus_content_in_prompt(fake_llm: FakeLLMClient) -> None:
    fake_llm.judge_response = json.dumps({"is_authentic": True, "rewritten_reply": "a reply"})

    verify_and_rephrase(fake_llm, _persona(), "a reply", focus_items=[_item(1, "bonjour")])

    system_prompt, user_prompt, _ = fake_llm.judge_calls[0]
    assert "Camille" in system_prompt
    assert "bonjour" in system_prompt
    assert "a reply" in user_prompt
