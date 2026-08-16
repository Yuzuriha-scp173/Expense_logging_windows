from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    override = os.environ.get("EXPENSE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return (Path(base) / "Daybook").resolve()
    return (Path.home() / "Library" / "Application Support" / "Daybook").resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: str = "fallback"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    expense_data_dir: Path = _default_data_dir()

    @property
    def db_path(self) -> Path:
        self.expense_data_dir.mkdir(parents=True, exist_ok=True)
        return self.expense_data_dir / "expenses.db"


def get_settings() -> Settings:
    return Settings()
