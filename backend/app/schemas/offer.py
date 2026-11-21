from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.campaign import CampaignOfferOut


class StreamOfferIn(BaseModel):
    offer_id: int = Field(gt=0)
    share: int = Field(ge=0, le=100)
    state: Literal["active", "disabled"] = "active"


def validate_offer_shares(offers: list[StreamOfferIn]) -> None:
    ids = [o.offer_id for o in offers]
    if len(ids) != len(set(ids)):
        raise ValueError("Оффер не может быть добавлен в поток дважды")
    active = [o for o in offers if o.state == "active"]
    if offers and not active:
        raise ValueError("В потоке должен быть хотя бы один активный оффер")
    total = sum(o.share for o in active)
    if active and total != 100:
        raise ValueError(f"Сумма долей активных офферов должна составлять 100% (сейчас {total}%)")


class CampaignOfferAdd(BaseModel):
    offer_id: int = Field(gt=0)
    stream_id: int | None = Field(default=None, gt=0, description="Поток; по умолчанию — первый поток с офферами")
    share: int | None = Field(
        default=None, ge=1, le=100, description="Доля нового оффера; без значения трафик делится поровну"
    )


class CampaignOffersUpdate(BaseModel):
    stream_id: int = Field(gt=0)
    offers: list[StreamOfferIn] = Field(min_length=1)
    expected_offer_ids: list[int] | None = Field(
        default=None,
        description="Offer ids the client saw in the stream. If the stream changed meanwhile, 409 is returned.",
    )

    @model_validator(mode="after")
    def _check(self) -> "CampaignOffersUpdate":
        validate_offer_shares(self.offers)
        return self


class OfferStreamSummary(BaseModel):
    stream_id: int
    name: str | None = None
    state: str | None = None
    total_share: int
    offers_count: int


class CampaignOffersResponse(BaseModel):
    campaign_id: int
    items: list[CampaignOfferOut]
    streams: list[OfferStreamSummary]


class OfferDistributeIn(BaseModel):
    stream_id: int = Field(gt=0)
    mode: Literal["equal", "normalize"] = Field(
        description="equal — split 100% equally between active offers; normalize — scale current shares to 100%"
    )
