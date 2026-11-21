from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.context import current_user_id
from app.core.exceptions import AuthenticationError
from app.core.security import InvalidTokenError, decode_access_token
from app.core.url_guard import URLGuard
from app.db.session import get_session
from app.integrations.keitaro.client import KeitaroClient
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.settings_service import ClientFactory, KeitaroConnection, SettingsService, default_client_factory

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False, description="Access token from POST /api/auth/login")


async def get_current_user(
    session: SessionDep, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise AuthenticationError("Сессия недействительна или истекла. Войдите заново.", code="invalid_token") from exc
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Пользователь не найден или отключён", code="invalid_token")
    current_user_id.set(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_client_factory() -> ClientFactory:
    """Overridable in tests to inject a mocked transport."""
    return default_client_factory


def get_url_guard() -> URLGuard:
    """Overridable in tests to inject a fake DNS resolver."""
    settings = get_settings()
    return URLGuard(allow_http=settings.keitaro_allow_http, allow_private=settings.keitaro_allow_private_hosts)


def get_settings_service(
    session: SessionDep,
    factory: Annotated[ClientFactory, Depends(get_client_factory)],
    guard: Annotated[URLGuard, Depends(get_url_guard)],
) -> SettingsService:
    return SettingsService(session, factory, guard)


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]


async def get_keitaro(settings_service: SettingsServiceDep) -> AsyncIterator[tuple[KeitaroClient, KeitaroConnection]]:
    client, conn = await settings_service.build_client()
    try:
        yield client, conn
    finally:
        await client.close()


KeitaroDep = Annotated[tuple[KeitaroClient, KeitaroConnection], Depends(get_keitaro)]
