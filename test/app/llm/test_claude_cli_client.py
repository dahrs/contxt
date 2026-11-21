from __future__ import annotations

import json
import subprocess

import pytest

from app.llm.claude_cli_client import ClaudeCliClient, ClaudeCliError, _strip_code_fence


def test__strip_code_fence_passes_through_plain_text() -> None:
    assert _strip_code_fence('{"a": 1}') == '{"a": 1}'


def test__strip_code_fence_unwraps_json_tagged_fence() -> None:
    fenced = '```json\n{"a": 1}\n```'

    assert _strip_code_fence(fenced) == '{"a": 1}'


def test__strip_code_fence_unwraps_untagged_fence() -> None:
    fenced = '```\n{"a": 1}\n```'

    assert _strip_code_fence(fenced) == '{"a": 1}'


def _fake_completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _success_payload(result: str, session_id: str = "session-1") -> str:
    return json.dumps({"result": result, "session_id": session_id, "is_error": False})


def test__judge_returns_fence_stripped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed(_success_payload('```json\n{"x": 1}\n```')))

    result = ClaudeCliClient().judge("system", "prompt")

    assert result == '{"x": 1}'


def test__generate_returns_text_and_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed(_success_payload("bonjour", "session-xyz")))

    text, session_id = ClaudeCliClient().generate("system", None, "salut")

    assert text == "bonjour"
    assert session_id == "session-xyz"


def test__run_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed("", returncode=1))

    with pytest.raises(ClaudeCliError):
        ClaudeCliClient().judge("system", "prompt")


def test__run_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="claude", timeout=60)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ClaudeCliError):
        ClaudeCliClient().judge("system", "prompt")


def test__run_raises_on_unparseable_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed("not json"))

    with pytest.raises(ClaudeCliError):
        ClaudeCliClient().judge("system", "prompt")


def test__run_raises_when_payload_reports_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"result": "boom", "session_id": "s1", "is_error": True})
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed(payload))

    with pytest.raises(ClaudeCliError):
        ClaudeCliClient().judge("system", "prompt")
