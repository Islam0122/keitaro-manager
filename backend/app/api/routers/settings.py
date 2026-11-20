from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsServiceDep
from app.repositories.campaign_log_repository import CampaignLogRepository
from app.schemas.settings import CampaignLogOut, ConnectionTestIn, ConnectionTestOut, SettingsOut, SettingsUpdate

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsOut, summary="Текущие настройки (API-ключ маскируется)")
async def get_settings(service: SettingsServiceDep) -> SettingsOut:
    return await service.get()


@router.put("/settings", response_model=SettingsOut, summary="Сохранить настройки")
async def update_settings(data: SettingsUpdate, service: SettingsServiceDep) -> SettingsOut:
    return await service.update(data)


@router.post("/settings/test", response_model=ConnectionTestOut, summary="Проверить подключение к Keitaro")
async def test_connection(service: SettingsServiceDep, data: ConnectionTestIn | None = None) -> ConnectionTestOut:
    return await service.test_connection(data or ConnectionTestIn())


@router.get("/logs", response_model=list[CampaignLogOut], summary="Журнал операций")
async def list_logs(
    session: SessionDep,
    campaign_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CampaignLogOut]:
    logs = await CampaignLogRepository(session).list(campaign_keitaro_id=campaign_id, limit=limit)
    return [CampaignLogOut.model_validate(log) for log in logs]
