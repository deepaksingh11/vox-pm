from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://voxpm:voxpm@localhost:5432/voxpm"
    environment: Literal["development", "production"] = "development"
    cors_origins: str = "http://localhost:5173"

    # LLM
    llm_provider: Literal["anthropic", "openai"] | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-6"

    # Voice
    deepgram_api_key: str = ""
    cartesia_api_key: str = ""
    cartesia_voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091"
    daily_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
