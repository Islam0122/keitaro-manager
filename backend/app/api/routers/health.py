import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep, SettingsServiceDep
from app.core.config import get_settings
from app.schemas.settings import HealthOut

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthOut, summary="Состояние приложения")
async def health(session: SessionDep, settings_service: SettingsServiceDep) -> HealthOut:
    database = "ok"
    configured = False
    try:
        await session.execute(text("SELECT 1"))
        configured = (await settings_service.resolve()).configured
    except Exception as exc:  # noqa: BLE001 - health must always answer
        logger.error("Health check database error: %s", exc)
        database = "error"
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        version=get_settings().app_version,
        database=database,
        keitaro_configured=configured,
    )
