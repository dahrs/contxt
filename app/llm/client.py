from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def generate(self, system_prompt: str, session_id: str | None, user_message: str) -> tuple[str, str]:
        """Produce the next conversational reply.

        `session_id` is None for the first turn of a conversation (the system prompt is used to
        start it) and the previously-returned session id for every later turn (the system prompt
        is then ignored - the underlying session already has it). Returns (reply_text, session_id)
        - callers must persist the returned session_id to pass back in on the next turn.
        """
        ...

    def judge(self, system_prompt: str, user_message: str, timeout_seconds: int | None = None) -> str:
        """One-off, non-conversational call (e.g. classifying how a message used target items, or
        a heavier one-off generation job). No session continuity - each call is independent.
        `timeout_seconds` overrides the configured default for callers that know a call will run
        long (e.g. generating several rich persona profiles) - the default stays tight so
        per-message chat calls fail fast rather than hang."""
        ...
