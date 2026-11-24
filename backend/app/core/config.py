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

    @model_validator(mode="after")
    def _forbid_placeholder_secret_in_production(self) -> "Settings":
        if self.environment == "production" and "change-me" in self.jwt_secret_key.lower():
            raise ValueError("JWT_SECRET_KEY must be replaced with a real secret in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
