from __future__ import annotations

import pytest

import app.conversation.signals as signals_module
from app.conversation.signals import ItemOutcomeEntry, apply_outcomes, extract_outcomes
from app.db.models import SkillItem, UserItemState
from app.srs.scheduler import introduce
from test.conftest import FakeLLMClient


def _item(id_: int) -> SkillItem:
    return SkillItem(
        id=id_, type="vocab", target_lang="fra", content=f"item-{id_}", level="A1", category=None, prerequisite_ids=[]
    )


def test__extract_outcomes_skips_llm_call_when_no_target_items(fake_llm: FakeLLMClient) -> None:
    outcomes = extract_outcomes(fake_llm, target_items=[], user_message="bonjour")

    assert outcomes == []
    assert fake_llm.judge_calls == []


def test__extract_outcomes_parses_valid_judge_response(fake_llm: FakeLLMClient) -> None:
    fake_llm.judge_response = '{"outcomes": [{"item_id": 1, "outcome": "correct"}]}'

    outcomes = extract_outcomes(fake_llm, target_items=[_item(1)], user_message="bonjour")

    assert len(outcomes) == 1
    assert outcomes[0].item_id == 1
    assert outcomes[0].outcome == "correct"


def test__extract_outcomes_returns_empty_on_unparseable_judge_response(fake_llm: FakeLLMClient) -> None:
    fake_llm.judge_response = "not json at all"

    outcomes = extract_outcomes(fake_llm, target_items=[_item(1)], user_message="bonjour")

    assert outcomes == []


def test__apply_outcomes_introduces_a_never_seen_item(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded_events: list[tuple[int, int, str]] = []
    upserted: list[UserItemState] = []
    monkeypatch.setattr(signals_module, "get_state", lambda user_id, item_id: None)
    monkeypatch.setattr(signals_module, "upsert_state", lambda state: upserted.append(state))
    monkeypatch.setattr(
        signals_module,
        "add_item_event",
        lambda message_id, item_id, outcome: recorded_events.append((message_id, item_id, outcome)),
    )

    apply_outcomes(user_id=1, message_id=10, outcomes=[ItemOutcomeEntry(item_id=5, outcome="correct")])

    assert recorded_events == [(10, 5, "correct")]
    assert len(upserted) == 1
    assert upserted[0].reps == 1
    assert upserted[0].lapses == 0


def test__apply_outcomes_avoided_outcome_counts_as_a_lapse(monkeypatch: pytest.MonkeyPatch) -> None:
    # A real fsrs_card_json (from introduce()), not a placeholder - review() needs to deserialize it.
    existing = introduce(1, 5)
    upserted: list[UserItemState] = []
    monkeypatch.setattr(signals_module, "get_state", lambda user_id, item_id: existing)
    monkeypatch.setattr(signals_module, "upsert_state", lambda state: upserted.append(state))
    monkeypatch.setattr(signals_module, "add_item_event", lambda message_id, item_id, outcome: None)

    apply_outcomes(user_id=1, message_id=10, outcomes=[ItemOutcomeEntry(item_id=5, outcome="avoided")])

    assert upserted[0].lapses == 1
