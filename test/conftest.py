from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import init_db
from app.main import app


@pytest.fixture(autouse=True)
def tmp_sqlite_db(tmp_path: Path) -> None:
    """Every test gets its own fresh, empty sqlite file - real DB I/O (not mocked), since that's
    the only meaningful way to verify a repository function's SQL/mapping is actually correct."""
    settings.data_dir = tmp_path
    init_db()


class FakeLLMClient:
    """Stands in for ClaudeCliClient in tests - no subprocess, no network, no cost. Tests
    configure `.generate_response`/`.judge_response` and can inspect `.generate_calls`/
    `.judge_calls` to assert what the function under test actually sent."""

    def __init__(self) -> None:
        self.generate_response: tuple[str, str] = ("a reply", "session-1")
        self.judge_response: str = '{"outcomes": []}'
        self.generate_calls: list[tuple[str, str | None, str]] = []
        self.judge_calls: list[tuple[str, str, int | None]] = []

    def generate(self, system_prompt: str, session_id: str | None, user_message: str) -> tuple[str, str]:
        self.generate_calls.append((system_prompt, session_id, user_message))
        return self.generate_response

    def judge(self, system_prompt: str, user_message: str, timeout_seconds: int | None = None) -> str:
        self.judge_calls.append((system_prompt, user_message, timeout_seconds))
        return self.judge_response


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def use_fake_llm(monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient) -> FakeLLMClient:
    """For acceptance tests driving real routes: swaps the app-wide LLM singleton so routes that
    call get_llm_client() transparently get the fake, without touching route code."""
    import app.llm as llm_module

    monkeypatch.setattr(llm_module, "_client", fake_llm)
    return fake_llm


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Drives the real FastAPI app (real routes, real DB via tmp_sqlite_db) for acceptance tests."""
    with TestClient(app) as test_client:
        yield test_client
