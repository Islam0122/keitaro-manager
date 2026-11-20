from fastapi import APIRouter

from app.api.deps import KeitaroDep
from app.schemas.keitaro import DomainOut, GroupOut, OfferOut, TrafficSourceOut
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("/domains", response_model=list[DomainOut], summary="Домены Keitaro")
async def domains(keitaro: KeitaroDep) -> list[DomainOut]:
    return await ResourceService(keitaro[0]).domains()


@router.get("/groups", response_model=list[GroupOut], summary="Группы кампаний Keitaro")
async def groups(keitaro: KeitaroDep) -> list[GroupOut]:
    return await ResourceService(keitaro[0]).groups("campaign")


@router.get("/sources", response_model=list[TrafficSourceOut], summary="Источники трафика Keitaro")
async def sources(keitaro: KeitaroDep) -> list[TrafficSourceOut]:
    return await ResourceService(keitaro[0]).sources()


@router.get("/offers", response_model=list[OfferOut], summary="Офферы Keitaro")
async def offers(keitaro: KeitaroDep) -> list[OfferOut]:
    return await ResourceService(keitaro[0]).offers()
