from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import IO, Any

import pytest

from app.config import settings
from app.curriculum.language_comparison import LanguageComparison, fetch_comparison, summarize_for_teaching

_REAL_COMPARISON_PAYLOAD: dict[str, Any] = {
    "categories": {
        "phonology": {"only_b": ["ɲ", "ɸ", "ɽ"]},
        "word_order": {
            "rows": [
                {"name": "subject-verb-object", "match": False},
                {"name": "adjective-noun", "match": True},
            ]
        },
        "morphology": {
            "cases": {"only_b": []},
            "tenses": {"only_b": ["non-past"]},
            "moods": {"only_b": ["volitional"]},
        },
        "writing_system": {"only_b": ["kanji", "hiragana", "katakana"]},
        "vocabulary_origin": {"shared": ["english"]},
    },
    "label": "very distant",
}


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test__fetch_comparison_returns_none_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lingdiff_api_url", "")

    assert fetch_comparison("eng", "jpn") is None


def test__fetch_comparison_returns_parsed_model_when_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lingdiff_api_url", "https://lingdiff.example.com")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda url, timeout: _FakeResponse(json.dumps(_REAL_COMPARISON_PAYLOAD).encode()),
    )

    comparison = fetch_comparison("eng", "jpn")

    assert comparison is not None
    assert comparison.label == "very distant"
    assert comparison.categories.phonology.only_b == ["ɲ", "ɸ", "ɽ"]


def test__fetch_comparison_returns_none_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lingdiff_api_url", "https://lingdiff.example.com")

    def raise_404(url: str, timeout: int) -> IO[bytes]:
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", raise_404)

    assert fetch_comparison("eng", "xyz") is None


def test__fetch_comparison_returns_none_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lingdiff_api_url", "https://lingdiff.example.com")

    def raise_connection_error(url: str, timeout: int) -> IO[bytes]:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", raise_connection_error)

    assert fetch_comparison("eng", "jpn") is None


def test__fetch_comparison_returns_none_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lingdiff_api_url", "https://lingdiff.example.com")
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: _FakeResponse(b"not json"))

    assert fetch_comparison("eng", "jpn") is None


def test__summarize_for_teaching_covers_all_present_categories() -> None:
    comparison = LanguageComparison.model_validate(_REAL_COMPARISON_PAYLOAD)

    summary = summarize_for_teaching(comparison)

    assert "very distant" in summary
    assert "ɲ, ɸ, ɽ" in summary
    assert "subject-verb-object" in summary
    assert "adjective-noun" not in summary  # matching features aren't a priority focus
    assert "non-past" in summary and "volitional" in summary
    assert "kanji" in summary
    assert "english" in summary


def test__summarize_for_teaching_omits_empty_categories() -> None:
    payload: dict[str, Any] = {
        "categories": {
            "phonology": {"only_b": []},
            "word_order": {"rows": [{"name": "adjective-noun", "match": True}]},
            "morphology": {"cases": {"only_b": []}, "tenses": {"only_b": []}, "moods": {"only_b": []}},
            "writing_system": {"only_b": []},
            "vocabulary_origin": {"shared": []},
        },
        "label": "close",
    }
    comparison = LanguageComparison.model_validate(payload)

    summary = summarize_for_teaching(comparison)

    assert summary == "Overall typological distance: close."
