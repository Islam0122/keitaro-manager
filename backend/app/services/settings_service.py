import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.core.logging import register_secret
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.core.url_guard import UnsafeURLError, URLGuard
from app.integrations.keitaro.client import KeitaroClient, build_base_url
from app.integrations.keitaro.exceptions import KeitaroError, KeitaroNotConfiguredError
from app.repositories.keitaro_config_repository import KeitaroConfigRepository
from app.schemas.settings import ConnectionTestIn, ConnectionTestOut, SettingsOut, SettingsUpdate
from app.services.audit import AuditLogger

ClientFactory = Callable[[str, str, float], KeitaroClient]


def default_client_factory(api_url: str, api_key: str, timeout: float) -> KeitaroClient:
    return KeitaroClient(api_url, api_key, timeout=timeout, retries=get_settings().keitaro_retries)


def same_endpoint(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return build_base_url(a).lower() == build_base_url(b).lower()


@dataclass(frozen=True)
class KeitaroConnection:
    api_url: str | None
    api_key: str | None
    timeout: float
    default_safe_url: str
    source: str

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_key)


class SettingsService:
    def __init__(
        self,
        session: AsyncSession,
        client_factory: ClientFactory = default_client_factory,
        guard: URLGuard | None = None,
    ) -> None:
        self.session = session
        self.repo = KeitaroConfigRepository(session)
        self.client_factory = client_factory
        self.guard = guard or URLGuard(
            allow_http=get_settings().keitaro_allow_http, allow_private=get_settings().keitaro_allow_private_hosts
        )

    async def resolve(self) -> KeitaroConnection:
        """DB settings take priority; environment variables are used as a fallback."""
        env = get_settings()
        config = await self.repo.get()
        db_url = config.api_url if config else None
        db_key = decrypt_secret(config.api_key_encrypted) if config and config.api_key_encrypted else None
        api_url = db_url or env.keitaro_api_url
        api_key = db_key or env.keitaro_api_key
        register_secret(api_key)
        if db_url and db_key:
            source = "database"
        elif api_url and api_key:
            source = "environment"
        else:
            source = "none"
        return KeitaroConnection(
            api_url=api_url,
            api_key=api_key,
            timeout=config.timeout if config else env.keitaro_timeout,
            default_safe_url=config.default_safe_url if config else env.default_safe_url,
            source=source,
        )

    async def build_client(self) -> tuple[KeitaroClient, KeitaroConnection]:
        conn = await self.resolve()
        if not conn.configured:
            raise KeitaroNotConfiguredError()
        # Re-validated on every use: DNS of an accepted host may have changed since it was saved.
        await self.guard.validate(conn.api_url)  # type: ignore[arg-type]
        return self.client_factory(conn.api_url, conn.api_key, conn.timeout), conn  # type: ignore[arg-type]

    async def get(self) -> SettingsOut:
        conn = await self.resolve()
        config = await self.repo.get()
        return SettingsOut(
            api_url=conn.api_url,
            api_key_set=bool(conn.api_key),
            api_key_masked=mask_secret(conn.api_key),
            timeout=conn.timeout,
            default_safe_url=conn.default_safe_url,
            source=conn.source,  # type: ignore[arg-type]
            updated_at=config.updated_at if config else None,
        )

    async def update(self, data: SettingsUpdate) -> SettingsOut:
        api_url = await self.guard.validate(data.api_url)
        config = await self.repo.get()
        current = await self.resolve()
        if not data.api_key and current.api_key and not same_endpoint(current.api_url, api_url):
            # Never silently re-use a stored key for a different host: that would leak it to whoever owns that host.
            raise ValidationAppError(
                "При смене API URL укажите API Key заново",
                errors=[{"field": "api_key", "message": "Укажите API Key для нового адреса"}],
            )
        fields: dict[str, object] = {
            "api_url": api_url,
            "timeout": data.timeout,
            "default_safe_url": data.default_safe_url,
        }
        if data.api_key:
            fields["api_key_encrypted"] = encrypt_secret(data.api_key)
            register_secret(data.api_key)
        elif config and config.api_key_encrypted:
            # re-encrypt with the current key derivation (transparently migrates legacy ciphertexts)
            fields["api_key_encrypted"] = encrypt_secret(decrypt_secret(config.api_key_encrypted))
        elif current.api_key:
            fields["api_key_encrypted"] = encrypt_secret(current.api_key)
        audit = AuditLogger(self.session)
        async with audit.track(
            "settings.update", details={"api_url": api_url, "api_key_changed": bool(data.api_key)}
        ):
            await self.repo.upsert(**fields)
            await self.session.commit()
        return await self.get()

    async def test_connection(self, data: ConnectionTestIn) -> ConnectionTestOut:
        conn = await self.resolve()
        api_url = data.api_url or conn.api_url
        api_key = (data.api_key or "").strip() or None
        if api_key is None:
            if data.api_url and not same_endpoint(data.api_url, conn.api_url):
                return ConnectionTestOut(ok=False, message="Для проверки нового адреса укажите API Key")
            api_key = conn.api_key
        if not api_url or not api_key:
            return ConnectionTestOut(ok=False, message="Укажите API URL и API Key")
        try:
            api_url = await self.guard.validate(api_url)
        except UnsafeURLError as exc:
            return ConnectionTestOut(ok=False, message=str(exc))
        register_secret(api_key)
        client = self.client_factory(api_url, api_key, conn.timeout)
        started = time.perf_counter()
        try:
            campaigns = await client.list_campaigns()
        except KeitaroError as exc:
            return ConnectionTestOut(ok=False, message=str(exc))
        finally:
            await client.close()
        latency = int((time.perf_counter() - started) * 1000)
        return ConnectionTestOut(
            ok=True, message="Подключение к Keitaro успешно", latency_ms=latency, campaigns_count=len(campaigns)
        )
