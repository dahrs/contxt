from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTXT_", env_file=".env")

    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    session_secret_key: str = "dev-secret-change-me"
    claude_cli_path: str = "claude"
    claude_model: str = "sonnet"
    claude_timeout_seconds: int = 60
    new_items_per_session: int = 2
    max_due_items_per_session: int = 5
    max_chronic_items_shown: int = 3
    relationship_summary_max_words: int = 120

    @property
    def db_path(self) -> Path:
        return self.data_dir / "contxt.sqlite3"


settings = Settings()
