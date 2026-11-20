import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ["KEITARO_API_URL"] = ""
os.environ["KEITARO_API_KEY"] = ""

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.api.deps import get_client_factory  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.integrations.keitaro.client import KeitaroClient  # noqa: E402
from app.main import app  # noqa: E402
from tests.fake_keitaro import API_KEY, FakeKeitaro  # noqa: E402


@pytest.fixture
def fake() -> FakeKeitaro:
    return FakeKeitaro()


@pytest.fixture
async def client(fake: FakeKeitaro):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def _session():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_client_factory] = lambda: (
        lambda url, key, timeout: KeitaroClient(url, key, timeout, transport=fake.transport())
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def configured(client: httpx.AsyncClient) -> httpx.AsyncClient:
    response = await client.put("/api/settings", json={"api_url": "https://tracker.example.com", "api_key": API_KEY})
    assert response.status_code == 200, response.text
    return client
