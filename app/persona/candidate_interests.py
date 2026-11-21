from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def sensitive_topics() -> frozenset[str]:
    """Political/religious topics from the shared candidate-interest list - excluded from
    shared_interest() matching so a persona never ends up volunteering one as conversational
    common ground, which would contradict the taboo-handling guardrail in the system prompt."""
    raw = resources.files("app.persona").joinpath("candidate_interests.json").read_text()
    data = json.loads(raw)
    return frozenset(item["topic"] for item in data["interests"] if item["sensitive"])
