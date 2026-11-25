"""Application configuration loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Strongly typed settings. Secrets have no defaults, so a missing value fails fast at startup."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Multiplayer Chess Platform API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = Field(..., description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host/db")

    jwt_secret_key: str = Field(..., min_length=MIN_SECRET_KEY_LENGTH)
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=60 * 24 * 7)

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Gameplay timing
    matchmaking_stale_seconds: float = Field(default=15, gt=0)
    game_start_timeout_seconds: float = Field(default=60, gt=0)
    sweeper_interval_seconds: float = Field(default=0.25, gt=0)
    clock_sync_interval_seconds: float = Field(default=5, gt=0)

    # WebSocket limits
    ws_auth_timeout_seconds: float = Field(default=10, gt=0)
    ws_idle_timeout_seconds: float = Field(default=60, gt=0)
    ws_send_timeout_seconds: float = Field(default=5, gt=0)
    ws_max_message_bytes: int = Field(default=4096, ge=256)
    ws_max_messages_per_second: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def _forbid_placeholder_secret_in_production(self) -> "Settings":
        if self.environment == "production" and "change-me" in self.jwt_secret_key.lower():
            raise ValueError("JWT_SECRET_KEY must be replaced with a real secret in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
