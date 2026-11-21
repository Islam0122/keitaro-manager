"""Integration tests against a REAL Keitaro instance.

They are skipped unless the following variables are set:

    KEITARO_IT_URL=https://your-tracker.example.com
    KEITARO_IT_API_KEY=...

Read-only checks run with just these two. Tests that create objects additionally need
KEITARO_IT_ALLOW_WRITE=1 plus ids of existing objects:

    KEITARO_IT_OFFER_ID, KEITARO_IT_OFFER_ID_2, KEITARO_IT_DOMAIN_ID, KEITARO_IT_GROUP_ID, KEITARO_IT_SOURCE_ID

Every created campaign is named "it-<random>" and is deleted (archived) at the end, even if the test fails.
Run:  pytest tests/integration -v
"""
import os
import secrets

import pytest

from app.integrations.keitaro.client import KeitaroClient
from app.schemas.keitaro import CampaignOut, DomainOut, GroupOut, OfferOut, StreamOut, TrafficSourceOut

URL = os.getenv("KEITARO_IT_URL")
KEY = os.getenv("KEITARO_IT_API_KEY")
WRITE = os.getenv("KEITARO_IT_ALLOW_WRITE") == "1"

pytestmark = pytest.mark.skipif(not (URL and KEY), reason="KEITARO_IT_URL / KEITARO_IT_API_KEY not set")


def _env_int(name: str) -> int:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} not set")
    return int(value)


@pytest.fixture
async def keitaro():
    client = KeitaroClient(URL, KEY, timeout=30)  # type: ignore[arg-type]
    yield client
    await client.close()


async def test_reference_lists_parse(keitaro):
    for raw, model in (
        (await keitaro.list_domains(), DomainOut),
        (await keitaro.list_groups("campaign"), GroupOut),
        (await keitaro.list_traffic_sources(), TrafficSourceOut),
        (await keitaro.list_offers(), OfferOut),
    ):
        for item in raw:
            model.model_validate(item)


async def test_campaigns_and_streams_parse(keitaro):
    campaigns = [CampaignOut.model_validate(c) for c in await keitaro.list_campaigns()]
    for campaign in campaigns[:5]:
        for stream in await keitaro.list_streams(campaign.id):
            StreamOut.model_validate(stream)


@pytest.mark.skipif(not WRITE, reason="KEITARO_IT_ALLOW_WRITE=1 not set")
async def test_create_campaign_with_two_streams_and_edit_offers(keitaro):
    """Runs the real CampaignService/OfferService against Keitaro (DB layer replaced by an in-memory SQLite)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.base import Base
    from app.schemas.campaign import CampaignCreate
    from app.schemas.offer import CampaignOfferAdd
    from app.services.campaign_service import CampaignService
    from app.services.offer_service import OfferService

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    data = CampaignCreate(
        name=f"it-{secrets.token_hex(4)}",
        country="US",
        offer_id=_env_int("KEITARO_IT_OFFER_ID"),
        domain_id=_env_int("KEITARO_IT_DOMAIN_ID"),
        group_id=_env_int("KEITARO_IT_GROUP_ID"),
        traffic_source_id=_env_int("KEITARO_IT_SOURCE_ID"),
    )
    campaign_id = None
    try:
        detail = await CampaignService(keitaro, session, "https://www.google.com").create(data)
        campaign_id = detail.campaign.id
        geo, offers = detail.streams
        assert geo.schema_ == "redirect" and geo.action_payload == "https://www.google.com"
        assert geo.filters[0].name == "country" and geo.filters[0].payload == ["US"]
        assert offers.schema_ == "landings" and offers.offers[0].share == 100
        assert detail.campaign.domain_id == data.domain_id and detail.campaign.group_id == data.group_id

        second = os.getenv("KEITARO_IT_OFFER_ID_2")
        if second:
            result = await OfferService(keitaro, session).add(campaign_id, CampaignOfferAdd(offer_id=int(second)))
            assert sorted(i.share for i in result.items) == [50, 50]
            result = await OfferService(keitaro, session).remove(campaign_id, int(second))
            assert [i.share for i in result.items] == [100]
    finally:
        if campaign_id is not None:
            await keitaro.delete_campaign(campaign_id)
        await session.close()
        await engine.dispose()
