from functools import lru_cache
from pathlib import Path
from typing import Literal  # kept for environment field

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root: config.py lives at apps/api/src/vox_pm/config.py → 4 levels up
_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://voxpm:voxpm@localhost:5432/voxpm"
    environment: Literal["development", "production"] = "development"
    cors_origins: str = "http://localhost:5173"

    # LLM — ordered comma-separated list, first with a valid key wins
    # e.g. LLM_PROVIDERS=anthropic,gemini,openai
    llm_providers: str = "anthropic,gemini,openai"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-2.0-flash"

    @property
    def llm_provider_order(self) -> list[str]:
        return [p.strip().lower() for p in self.llm_providers.split(",") if p.strip()]

    # Voice
    deepgram_api_key: str = ""
    cartesia_api_key: str = ""
    cartesia_voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091"
    daily_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        # Filter empty strings: a trailing comma yields "" which would allow all origins.
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
