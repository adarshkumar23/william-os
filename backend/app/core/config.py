"""
WILLIAM OS — Application Configuration
All settings from environment with validated defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # ── App ──────────────────────────────────────────────────────
    app_name: str = "WILLIAM OS"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    base_url: str = "http://localhost:8000"

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://william:william@localhost:5432/williamos"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 300

    # ── Auth ─────────────────────────────────────────────────────
    jwt_secret_key: SecretStr = Field(default=SecretStr("CHANGE-ME-IN-PRODUCTION"))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ── Encryption ───────────────────────────────────────────────
    encryption_master_salt: SecretStr = Field(default=SecretStr("CHANGE-ME"))
    encryption_iterations: int = 600_000

    # ── AI ────────────────────────────────────────────────────────
    gemini_api_key: SecretStr = Field(default=SecretStr(""))
    gemini_model: str = "gemini-2.0-flash"
    openrouter_api_key: SecretStr = Field(default=SecretStr(""))
    openrouter_model: str = "meta-llama/llama-3.1-70b-instruct"
    whisper_api_key: SecretStr = Field(default=SecretStr(""))

    # ── Email ────────────────────────────────────────────────────
    gmail_client_id: str = ""
    gmail_client_secret: SecretStr = Field(default=SecretStr(""))

    # ── Messaging ────────────────────────────────────────────────
    telegram_bot_token: SecretStr = Field(default=SecretStr(""))

    # ── CORS ─────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Scheduling ───────────────────────────────────────────────
    schedule_regen_cron: str = "0 0 * * *"
    prewake_offset_minutes: int = 30

    # ── Observability ───────────────────────────────────────────
    metrics_enabled: bool = True
    sentry_dsn: SecretStr = Field(default=SecretStr(""))
    sentry_traces_sample_rate: float = 0.1

    # ── Experimentation ─────────────────────────────────────────
    experiment_rollout_seed: str = "william-os"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
