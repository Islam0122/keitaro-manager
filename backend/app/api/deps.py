from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.integrations.keitaro.client import KeitaroClient
from app.services.settings_service import ClientFactory, KeitaroConnection, SettingsService, default_client_factory

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_client_factory() -> ClientFactory:
    """Overridable in tests to inject a mocked transport."""
    return default_client_factory


def get_settings_service(
    session: SessionDep, factory: Annotated[ClientFactory, Depends(get_client_factory)]
) -> SettingsService:
    return SettingsService(session, factory)


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]


async def get_keitaro(settings_service: SettingsServiceDep) -> AsyncIterator[tuple[KeitaroClient, KeitaroConnection]]:
    client, conn = await settings_service.build_client()
    try:
        yield client, conn
    finally:
        await client.close()


KeitaroDep = Annotated[tuple[KeitaroClient, KeitaroConnection], Depends(get_keitaro)]
