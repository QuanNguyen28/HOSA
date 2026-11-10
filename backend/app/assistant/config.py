from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AssistantSettings(BaseSettings):
    assistant_enabled: bool = False
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = ""
    openrouter_timeout_seconds: float = Field(default=30, gt=0, le=120)
    openrouter_max_tokens: int = Field(default=1800, ge=128, le=8192)
    openrouter_response_format: str = Field(default="json_schema", pattern="^(json_schema|json_object)$")
    assistant_draft_ttl_seconds: int = Field(default=900, ge=30, le=3600)
    assistant_max_drafts: int = Field(default=128, ge=1, le=1024)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore"
    )


@lru_cache
def get_assistant_settings() -> AssistantSettings:
    return AssistantSettings()
