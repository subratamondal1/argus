"""Typed runtime configuration via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARGUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = Field(
        default="anthropic/claude-sonnet-4-6",
        description="LiteLLM model id used by the agent loop.",
    )
    request_timeout_s: float = Field(default=30.0, gt=0)
    searxng_url: str = Field(
        default="http://localhost:8080",
        description="Base URL of the SearXNG instance.",
    )
    max_turns: int = Field(default=8, gt=0, description="Maximum LLM turns per run.")
    max_tokens: int = Field(default=120_000, gt=0, description="Maximum cumulative tokens per run.")
    max_wallclock_s: float = Field(
        default=180.0, gt=0, description="Maximum wall-clock seconds per run."
    )
    max_cost_usd: float = Field(default=0.50, gt=0, description="Hard cost cap per run in USD.")
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False, description="Emit JSON logs.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
