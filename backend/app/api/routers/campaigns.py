from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import KeitaroDep, SessionDep
from app.schemas.campaign import CampaignCreate, CampaignDetail, CampaignListResponse, CampaignUpdate
from app.schemas.keitaro import StreamOut
from app.schemas.offer import CampaignOfferAdd, CampaignOffersResponse, CampaignOffersUpdate
from app.schemas.stream import StreamIn
from app.services.campaign_service import CampaignService
from app.services.offer_service import OfferService
from app.services.stream_service import StreamService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _campaigns(keitaro: KeitaroDep, session: SessionDep) -> CampaignService:
    client, conn = keitaro
    return CampaignService(client, session, conn.default_safe_url)


@router.get("", response_model=CampaignListResponse, summary="Список кампаний")
async def list_campaigns(
    keitaro: KeitaroDep,
    session: SessionDep,
    search: Annotated[str | None, Query(max_length=255, description="Поиск по названию, alias или ID")] = None,
    group_id: Annotated[int | None, Query(gt=0)] = None,
    state: Literal["active", "disabled", "deleted"] | None = None,
    with_offers: bool = True,
) -> CampaignListResponse:
    return await _campaigns(keitaro, session).list_campaigns(
        search=search, group_id=group_id, state=state, with_offers=with_offers
    )


@router.post("", response_model=CampaignDetail, status_code=status.HTTP_201_CREATED, summary="Создать кампанию")
async def create_campaign(data: CampaignCreate, keitaro: KeitaroDep, session: SessionDep) -> CampaignDetail:
    return await _campaigns(keitaro, session).create(data)


@router.get("/{campaign_id}", response_model=CampaignDetail, summary="Кампания с потоками и офферами")
async def get_campaign(campaign_id: int, keitaro: KeitaroDep, session: SessionDep) -> CampaignDetail:
    return await _campaigns(keitaro, session).get_detail(campaign_id)


@router.put("/{campaign_id}", response_model=CampaignDetail, summary="Обновить кампанию")
async def update_campaign(
    campaign_id: int, data: CampaignUpdate, keitaro: KeitaroDep, session: SessionDep
) -> CampaignDetail:
    return await _campaigns(keitaro, session).update(campaign_id, data)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить кампанию (в архив Keitaro)")
async def delete_campaign(campaign_id: int, keitaro: KeitaroDep, session: SessionDep) -> Response:
    await _campaigns(keitaro, session).delete(campaign_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- offers
@router.get("/{campaign_id}/offers", response_model=CampaignOffersResponse, summary="Офферы кампании")
async def list_offers(campaign_id: int, keitaro: KeitaroDep, session: SessionDep) -> CampaignOffersResponse:
    return await OfferService(keitaro[0], session).list(campaign_id)


@router.post("/{campaign_id}/offers", response_model=CampaignOffersResponse, summary="Добавить оффер в поток")
async def add_offer(
    campaign_id: int, data: CampaignOfferAdd, keitaro: KeitaroDep, session: SessionDep
) -> CampaignOffersResponse:
    return await OfferService(keitaro[0], session).add(campaign_id, data)


@router.put("/{campaign_id}/offers", response_model=CampaignOffersResponse, summary="Изменить распределение трафика")
async def update_offers(
    campaign_id: int, data: CampaignOffersUpdate, keitaro: KeitaroDep, session: SessionDep
) -> CampaignOffersResponse:
    return await OfferService(keitaro[0], session).update(campaign_id, data)


@router.delete("/{campaign_id}/offers/{offer_id}", response_model=CampaignOffersResponse, summary="Удалить оффер")
async def remove_offer(
    campaign_id: int,
    offer_id: int,
    keitaro: KeitaroDep,
    session: SessionDep,
    stream_id: Annotated[int | None, Query(gt=0)] = None,
) -> CampaignOffersResponse:
    return await OfferService(keitaro[0], session).remove(campaign_id, offer_id, stream_id)


# --------------------------------------------------------------- streams
@router.get("/{campaign_id}/streams", response_model=list[StreamOut], summary="Потоки кампании")
async def list_streams(campaign_id: int, keitaro: KeitaroDep, session: SessionDep) -> list[StreamOut]:
    return await StreamService(keitaro[0], session).list(campaign_id)


@router.post(
    "/{campaign_id}/streams", response_model=StreamOut, status_code=status.HTTP_201_CREATED, summary="Создать поток"
)
async def create_stream(campaign_id: int, data: StreamIn, keitaro: KeitaroDep, session: SessionDep) -> StreamOut:
    return await StreamService(keitaro[0], session).create(campaign_id, data)
