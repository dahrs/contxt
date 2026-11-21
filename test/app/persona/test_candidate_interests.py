from __future__ import annotations

import json
from importlib import resources

from app.persona.candidate_interests import sensitive_topics


def test__sensitive_topics_matches_sensitive_entries_in_the_real_file() -> None:
    raw = resources.files("app.persona").joinpath("candidate_interests.json").read_text()
    data = json.loads(raw)
    expected = {item["topic"] for item in data["interests"] if item["sensitive"]}

    assert sensitive_topics() == expected
    assert len(expected) > 0


def test__sensitive_topics_excludes_non_sensitive_entries() -> None:
    raw = resources.files("app.persona").joinpath("candidate_interests.json").read_text()
    data = json.loads(raw)
    some_non_sensitive = next(item["topic"] for item in data["interests"] if not item["sensitive"])

    assert some_non_sensitive not in sensitive_topics()


def test__sensitive_topics_is_cached() -> None:
    assert sensitive_topics() is sensitive_topics()
