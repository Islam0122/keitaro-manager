import os

os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-0123456789"
os.environ["KEITARO_API_URL"] = ""
os.environ["KEITARO_API_KEY"] = ""
os.environ["KEITARO_ALLOW_HTTP"] = "false"
os.environ["KEITARO_ALLOW_PRIVATE_HOSTS"] = "false"
os.environ["ADMIN_USERNAME"] = ""
os.environ["ADMIN_PASSWORD"] = ""

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_client_factory, get_url_guard
from app.core.security import hash_password
from app.core.url_guard import URLGuard
from app.db.base import Base
from app.db.session import get_session
from app.integrations.keitaro.client import KeitaroClient
from app.main import app
from app.models import User
from tests.fake_keitaro import API_KEY, FakeKeitaro

TRACKER_URL = "https://tracker.example.com"
USERNAME = "admin"
PASSWORD = "Correct-horse-42"

# Fake DNS: public tracker, and names that point into private/metadata ranges.
DNS = {
    "tracker.example.com": ["93.184.216.34"],
    "other.example.com": ["93.184.216.35"],
    "evil-internal.example.com": ["10.0.0.5"],
    "rebind.example.com": ["93.184.216.36", "127.0.0.1"],
    "metadata-alias.example.com": ["169.254.169.254"],
}


async def fake_resolver(host: str, port: int) -> list[str]:
    if host not in DNS:
        raise OSError("Name or service not known")
    return DNS[host]


@pytest.fixture
def fake() -> FakeKeitaro:
    return FakeKeitaro()


@pytest.fixture
async def sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.fixture
async def anon(fake: FakeKeitaro, sessions):
    """HTTP client without credentials."""

    async def _session():
        async with sessions() as session:
            yield session

    async with sessions() as session:
        session.add(User(username=USERNAME, password_hash=hash_password(PASSWORD), is_active=True))
        await session.commit()

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_url_guard] = lambda: URLGuard(resolver=fake_resolver)
    app.dependency_overrides[get_client_factory] = lambda: (
        lambda url, key, timeout: KeitaroClient(url, key, timeout, transport=fake.transport(), retries=0)
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
async def client(anon: httpx.AsyncClient) -> httpx.AsyncClient:
    """Authenticated HTTP client."""
    response = await anon.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200, response.text
    anon.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return anon


@pytest.fixture
async def configured(client: httpx.AsyncClient) -> httpx.AsyncClient:
    response = await client.put("/api/settings", json={"api_url": TRACKER_URL, "api_key": API_KEY})
    assert response.status_code == 200, response.text
    return client
