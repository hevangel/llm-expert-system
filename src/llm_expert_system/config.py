"""Typed application configuration with environment-only secret handling."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Values use the ``LLM_EXPERT_`` environment prefix."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_EXPERT_", env_file=".env", extra="ignore", case_sensitive=False
    )

    workspace: Path = Path(".llm-expert")
    provider: str = "fake"
    model: str = "fake/deterministic"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_token: str | None = Field(default=None, repr=False)
    execution_mode: Literal["local", "container"] = "local"
    max_source_bytes: int = Field(default=1_048_576, ge=1, le=100_000_000)
    query_timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    max_output_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    max_models: int = Field(default=10, ge=1, le=1000)

    @field_validator("workspace", mode="after")
    @classmethod
    def normalize_workspace(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def requires_authentication(self) -> bool:
        return self.api_host not in {"127.0.0.1", "localhost", "::1"}

    def validate_security(self) -> None:
        if self.requires_authentication and not self.api_token:
            raise ValueError("LLM_EXPERT_API_TOKEN is required when binding beyond loopback")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
