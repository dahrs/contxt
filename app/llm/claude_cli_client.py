from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*)\n```\s*$", re.DOTALL)


class ClaudeCliError(Exception):
    """Raised when the `claude` CLI subprocess fails or returns an unusable result."""


def _strip_code_fence(text: str) -> str:
    """The model sometimes wraps JSON asked for in `judge()` in a markdown code fence
    even when told to respond with JSON only - unwrap it if present."""
    match = _CODE_FENCE_RE.match(text.strip())
    return match.group(1) if match else text


@dataclass
class _CliResult:
    text: str
    session_id: str


def _run(prompt: str, *, system_prompt: str | None, resume_session_id: str | None, timeout_seconds: int) -> _CliResult:
    args = [
        settings.claude_cli_path,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        settings.claude_model,
        "--restricted",
        "--strict-mcp-config",
    ]
    if resume_session_id is not None:
        args += ["--resume", resume_session_id]
    elif system_prompt is not None:
        args += ["--system-prompt", system_prompt]

    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        log.exception("claude CLI call timed out after %s seconds", timeout_seconds)
        raise ClaudeCliError("claude CLI call timed out") from exc

    if completed.returncode != 0:
        log.error("claude CLI exited with status %s: %s", completed.returncode, completed.stderr)
        raise ClaudeCliError(f"claude CLI exited with status {completed.returncode}: {completed.stderr}")

    try:
        payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        log.exception("claude CLI returned non-JSON output: %r", completed.stdout)
        raise ClaudeCliError("claude CLI returned unparseable output") from exc

    if payload.get("is_error"):
        log.error("claude CLI reported an error result: %s", payload)
        raise ClaudeCliError(f"claude CLI reported an error: {payload.get('result')!r}")

    result_text = payload.get("result")
    session_id = payload.get("session_id")
    if not isinstance(result_text, str) or not isinstance(session_id, str):
        raise ClaudeCliError(f"unexpected claude CLI JSON shape: {payload}")

    return _CliResult(text=result_text, session_id=session_id)


class ClaudeCliClient:
    """LLMClient implementation that shells out to the `claude` CLI, reusing its authenticated
    session rather than calling the hosted Anthropic API with a metered key."""

    def generate(self, system_prompt: str, session_id: str | None, user_message: str) -> tuple[str, str]:
        result = _run(
            user_message,
            system_prompt=system_prompt,
            resume_session_id=session_id,
            timeout_seconds=settings.claude_timeout_seconds,
        )
        return result.text, result.session_id

    def judge(self, system_prompt: str, user_message: str, timeout_seconds: int | None = None) -> str:
        result = _run(
            user_message,
            system_prompt=system_prompt,
            resume_session_id=None,
            timeout_seconds=timeout_seconds or settings.claude_timeout_seconds,
        )
        return _strip_code_fence(result.text)
