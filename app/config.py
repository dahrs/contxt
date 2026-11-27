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
    max_engagement_topics_shown: int = 2
    relationship_summary_max_words: int = 120
    proactive_min_gap_hours: int = 20
    milestone_unlock_threshold: float = 0.7
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    lingdiff_api_url: str = ""

    @property
    def db_path(self) -> Path:
        return self.data_dir / "contxt.sqlite3"


settings = Settings()
