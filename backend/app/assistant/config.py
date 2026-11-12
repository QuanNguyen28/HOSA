from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AssistantSettings(BaseSettings):
    assistant_enabled: bool = False
    assistant_provider: str = Field(default="nvidia", pattern="^(nvidia|gemini|openrouter)$")
    nvidia_api_key: SecretStr | None = None
    nvidia_model: str = "deepseek-ai/deepseek-v4.1-flash"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_max_output_tokens: int = Field(default=1048576, ge=1024, le=1048576)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_max_output_tokens: int = Field(default=65536, ge=1024, le=65536)
    assistant_streaming: bool = True
    assistant_failover_enabled: bool = True
    assistant_connect_timeout_seconds: float = Field(default=15, gt=0, le=60)
    assistant_retry_base_seconds: float = Field(default=60, ge=1, le=3600)
    assistant_max_concurrent_per_provider: int = Field(default=1, ge=1, le=16)
    assistant_database_path: str = ""
    lunarsight_raw_dataset_path: str = Field(default="", validation_alias="LUNARSIGHT_RAW_DATASET_PATH")
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = ""
    openrouter_reasoning_enabled: bool | None = None
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
