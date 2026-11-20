from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _check_url(value: str) -> str:
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        raise ValueError("URL должен начинаться с http:// или https://")
    return value.rstrip("/")


class SettingsOut(BaseModel):
    api_url: str | None
    api_key_set: bool
    api_key_masked: str | None
    timeout: float
    default_safe_url: str
    source: Literal["database", "environment", "none"]
    updated_at: datetime | None = None


class SettingsUpdate(BaseModel):
    api_url: str
    api_key: str | None = Field(default=None, description="Пустое значение — оставить текущий ключ")
    timeout: float = Field(default=15.0, gt=0, le=120)
    default_safe_url: str = "https://www.google.com"

    _url = field_validator("api_url", "default_safe_url")(_check_url)

    @field_validator("api_key")
    @classmethod
    def _key(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None


class ConnectionTestIn(BaseModel):
    api_url: str | None = None
    api_key: str | None = None

    @field_validator("api_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return _check_url(value) if value else None


class ConnectionTestOut(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None
    campaigns_count: int | None = None


class HealthOut(BaseModel):
    status: str
    version: str
    database: str
    keitaro_configured: bool


class CampaignLogOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    campaign_keitaro_id: int | None
    action: str
    status: str
    message: str | None
    details: dict | None
    created_at: datetime
