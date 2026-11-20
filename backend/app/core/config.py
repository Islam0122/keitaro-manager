"""Application settings loaded from environment variables (.env)."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Keitaro Manager"
    app_version: str = "1.0.0"
    environment: str = "production"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_manager"

    # Used to encrypt the Keitaro API key stored in the database. Required, never hard-coded.
    secret_key: str = Field(..., min_length=16)

    # Comma separated list of allowed CORS origins (only needed when frontend runs on another origin).
    cors_origins: str = "http://localhost:5173"

    # Optional fallback connection (used when nothing is saved in the Settings page).
    keitaro_api_url: str | None = None
    keitaro_api_key: str | None = None
    keitaro_timeout: float = Field(default=15.0, gt=0, le=120)
    keitaro_max_concurrency: int = Field(default=8, ge=1, le=50)

    # Redirect URL for the "GEO" stream created by the Campaign Creator.
    default_safe_url: str = "https://www.google.com"

    @field_validator("keitaro_api_url", "keitaro_api_key", mode="before")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
