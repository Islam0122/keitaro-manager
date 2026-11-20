from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.keitaro import StreamOut


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(description="ISO 3166-1 alpha-2 код страны, например US")
    offer_id: int = Field(gt=0)
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название кампании не может быть пустым")
        return value

    @field_validator("country")
    @classmethod
    def _country(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 2 or not value.isascii() or not value.isalpha():
            raise ValueError("Укажите двухбуквенный ISO-код страны (например, US)")
        return value


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    group_id: int | None = Field(default=None, gt=0)
    traffic_source_id: int | None = Field(default=None, gt=0)
    domain_id: int | None = Field(default=None, gt=0)
    state: Literal["active", "disabled"] | None = None


class CampaignListItem(BaseModel):
    id: int
    alias: str | None = None
    name: str
    type: str | None = None
    state: str | None = None
    group_id: int | None = None
    group_name: str | None = None
    traffic_source_id: int | None = None
    traffic_source_name: str | None = None
    domain_id: int | None = None
    domain_name: str | None = None
    streams_count: int | None = None
    offers_count: int | None = None
    updated_at: str | None = None


class CampaignListResponse(BaseModel):
    items: list[CampaignListItem]
    total: int
    offers_total: int | None = None


class CampaignOfferOut(BaseModel):
    stream_id: int
    stream_name: str | None = None
    offer_id: int
    offer_name: str | None = None
    share: int
    state: str


class LocalCampaignInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country: str
    offer_id: int
    geo_stream_id: int | None = None
    offer_stream_id: int | None = None
    created_at: datetime


class CampaignDetail(BaseModel):
    campaign: CampaignListItem
    streams: list[StreamOut]
    offers: list[CampaignOfferOut]
    local: LocalCampaignInfo | None = None
