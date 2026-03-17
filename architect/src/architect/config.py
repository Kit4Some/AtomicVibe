"""Central configuration for ARCHITECT using Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ARCHITECT application settings.

    All values can be overridden via environment variables prefixed with ``ARCHITECT_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="ARCHITECT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    openai_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")
    default_model: str = "claude-sonnet-4-6"
    tier: str = "mid"

    # --- Budget ---
    max_cost_usd: float = Field(default=50.0, ge=0.0)
    max_total_iterations: int = Field(default=30, ge=1)
    max_sprint_iterations: int = Field(default=5, ge=1)

    # --- Paths ---
    workspace_path: Path = Path("./workspace")
    vibe_path: Path = Path("./.vibe")

    # --- UI ---
    host: str = "0.0.0.0"
    port: int = Field(default=18080, ge=1, le=65535)

    # --- Logging ---
    log_format: str = Field(default="console", pattern="^(json|console)$")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


settings: Settings = get_settings()
