from __future__ import annotations

from app.llm.claude_cli_client import ClaudeCliClient
from app.llm.client import LLMClient

_client: LLMClient = ClaudeCliClient()


def get_llm_client() -> LLMClient:
    return _client
