"""Pydantic models describing Keitaro Admin API objects (only the fields used by the app)."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KeitaroModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DomainOut(KeitaroModel):
    id: int
    name: str
    state: str | None = None
    network_status: str | None = None
    default_campaign_id: int | None = None
    is_ssl: bool | None = None


class GroupOut(KeitaroModel):
    id: int
    name: str
    type: str | None = None


class TrafficSourceOut(KeitaroModel):
    id: int
    name: str
    state: str | None = None


class OfferOut(KeitaroModel):
    id: int
    name: str
    group_id: int | None = None
    state: str | None = None
    country: list[str] = Field(default_factory=list)
    payout_value: float | None = None
    payout_currency: str | None = None
    action_type: str | None = None
    action_payload: Any = None

    @field_validator("country", mode="before")
    @classmethod
    def _country(cls, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [c.strip() for c in value.split(",") if c.strip()]
        return [str(c) for c in value]

    @field_validator("payout_value", mode="before")
    @classmethod
    def _payout(cls, value: Any) -> float | None:
        return _to_float(value)


class StreamFilterOut(KeitaroModel):
    id: int | None = None
    name: str
    mode: str = "accept"
    payload: Any = None


class StreamOfferOut(KeitaroModel):
    id: int | None = None
    offer_id: int
    share: int = 0
    state: str = "active"

    @field_validator("share", mode="before")
    @classmethod
    def _share(cls, value: Any) -> int:
        number = _to_float(value)
        return int(round(number)) if number is not None else 0


class StreamOut(KeitaroModel):
    id: int
    campaign_id: int
    name: str | None = None
    type: str | None = None
    position: int | None = None
    weight: int | None = None
    state: str | None = None
    schema_: str | None = Field(default=None, alias="schema")
    action_type: str | None = None
    action_payload: Any = None
    filter_or: bool = False
    collect_clicks: bool = True
    comments: str | None = None
    filters: list[StreamFilterOut] = Field(default_factory=list)
    offers: list[StreamOfferOut] = Field(default_factory=list)
    landings: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("filters", "offers", "landings", mode="before")
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        return value or []


class CampaignOut(KeitaroModel):
    id: int
    alias: str | None = None
    name: str
    type: str | None = None
    state: str | None = None
    group_id: int | None = None
    traffic_source_id: int | None = None
    domain_id: int | None = None
    token: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
