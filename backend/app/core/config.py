"""Application settings loaded from environment variables (.env)."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Keitaro Manager"
    app_version: str = "1.1.0"
    environment: str = "production"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_manager"

    # Master secret. Independent sub-keys for JWT signing and for encrypting the Keitaro API key
    # are derived from it with HKDF (see app.core.security). Required, never hard-coded.
    secret_key: str = Field(..., min_length=32)

    # Comma separated list of allowed CORS origins (only needed when the frontend runs on another origin).
    cors_origins: str = "http://localhost:5173"

    # --- authentication
    access_token_ttl_minutes: int = Field(default=720, ge=5, le=60 * 24 * 7)
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)
    # Optional bootstrap admin: created on startup if a user with this name does not exist yet.
    admin_username: str | None = None
    admin_password: str | None = None

    # --- Keitaro connection (fallback when nothing is saved on the Settings page)
    keitaro_api_url: str | None = None
    keitaro_api_key: str | None = None
    keitaro_timeout: float = Field(default=15.0, gt=0, le=120)
    keitaro_max_concurrency: int = Field(default=8, ge=1, le=50)
    keitaro_retries: int = Field(default=2, ge=0, le=5)
    # SSRF protection. Plain http sends the API key unencrypted, so it is opt-in.
    keitaro_allow_http: bool = False
    # Only for local development against a tracker on a private network. Never enable on a public server.
    keitaro_allow_private_hosts: bool = False

    # Redirect URL for the "GEO" stream created by the Campaign Creator.
    default_safe_url: str = "https://www.google.com"

    @field_validator("keitaro_api_url", "keitaro_api_key", "admin_username", "admin_password", mode="before")
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
