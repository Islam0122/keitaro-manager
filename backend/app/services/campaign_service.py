"""Campaign use cases. Keitaro is the source of truth, the local DB keeps creation history and audit logs."""
import asyncio
import logging
import secrets
import string
from collections.abc import Awaitable, Iterable
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.integrations.keitaro.client import KeitaroClient
from app.integrations.keitaro.exceptions import KeitaroError, KeitaroNotFoundError
from app.repositories.campaign_repository import CampaignRepository
from app.schemas.campaign import (
    CampaignCreate,
    CampaignDetail,
    CampaignListItem,
    CampaignListResponse,
    CampaignOfferOut,
    CampaignUpdate,
    LocalCampaignInfo,
)
from app.schemas.keitaro import CampaignOut, DomainOut, GroupOut, OfferOut, StreamOut, TrafficSourceOut
from app.services.audit import AuditLogger

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _names(items: Iterable[Any]) -> dict[int, str]:
    return {item.id: item.name for item in items}


async def _tolerant(coro: Awaitable[T], default: T, what: str) -> T:
    try:
        return await coro
    except KeitaroError as exc:
        logger.warning("Could not load %s from Keitaro: %s", what, exc)
        return default


def generate_alias(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def sort_streams(streams: list[StreamOut]) -> list[StreamOut]:
    type_order = {"forced": 0, "regular": 1, "default": 2}
    return sorted(streams, key=lambda s: (type_order.get(s.type or "", 1), s.position or 0, s.id))


def collect_offers(streams: list[StreamOut], offer_names: dict[int, str]) -> list[CampaignOfferOut]:
    result: list[CampaignOfferOut] = []
    for stream in streams:
        for offer in stream.offers:
            result.append(
                CampaignOfferOut(
                    stream_id=stream.id,
                    stream_name=stream.name,
                    offer_id=offer.offer_id,
                    offer_name=offer_names.get(offer.offer_id),
                    share=offer.share,
                    state=offer.state,
                )
            )
    return result


class CampaignService:
    def __init__(self, client: KeitaroClient, session: AsyncSession, safe_url: str) -> None:
        self.client = client
        self.session = session
        self.safe_url = safe_url
        self.repo = CampaignRepository(session)
        self.audit = AuditLogger(session)

    # ------------------------------------------------------------------ read
    async def _lookups(self) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
        groups, sources, domains = await asyncio.gather(
            _tolerant(self.client.list_groups("campaign"), [], "groups"),
            _tolerant(self.client.list_traffic_sources(), [], "traffic sources"),
            _tolerant(self.client.list_domains(), [], "domains"),
        )
        return (
            _names(GroupOut.model_validate(g) for g in groups),
            _names(TrafficSourceOut.model_validate(s) for s in sources),
            _names(DomainOut.model_validate(d) for d in domains),
        )

    @staticmethod
    def _to_item(
        campaign: CampaignOut,
        lookups: tuple[dict[int, str], dict[int, str], dict[int, str]],
        streams: list[StreamOut] | None = None,
    ) -> CampaignListItem:
        groups, sources, domains = lookups
        return CampaignListItem(
            **campaign.model_dump(include=set(CampaignListItem.model_fields) & set(CampaignOut.model_fields)),
            group_name=groups.get(campaign.group_id) if campaign.group_id else None,
            traffic_source_name=sources.get(campaign.traffic_source_id) if campaign.traffic_source_id else None,
            domain_name=domains.get(campaign.domain_id) if campaign.domain_id else None,
            streams_count=len(streams) if streams is not None else None,
            offers_count=len({o.offer_id for s in streams for o in s.offers}) if streams is not None else None,
        )

    async def list_campaigns(
        self,
        *,
        search: str | None = None,
        group_id: int | None = None,
        state: str | None = None,
        with_offers: bool = True,
    ) -> CampaignListResponse:
        raw, lookups = await asyncio.gather(self.client.list_campaigns(), self._lookups())
        campaigns = [CampaignOut.model_validate(c) for c in raw]

        if state:
            campaigns = [c for c in campaigns if c.state == state]
        else:
            campaigns = [c for c in campaigns if c.state != "deleted"]
        if group_id is not None:
            campaigns = [c for c in campaigns if c.group_id == group_id]
        if search and search.strip():
            needle = search.strip().casefold()
            campaigns = [
                c
                for c in campaigns
                if needle in c.name.casefold() or needle == str(c.id) or needle in (c.alias or "").casefold()
            ]

        streams_by_campaign: dict[int, list[StreamOut] | None] = {}
        if with_offers and campaigns:
            semaphore = asyncio.Semaphore(get_settings().keitaro_max_concurrency)

            async def load(campaign_id: int) -> None:
                async with semaphore:
                    try:
                        data = await self.client.list_streams(campaign_id)
                        streams_by_campaign[campaign_id] = [StreamOut.model_validate(s) for s in data]
                    except KeitaroError as exc:
                        logger.warning("Could not load streams of campaign %s: %s", campaign_id, exc)
                        streams_by_campaign[campaign_id] = None

            await asyncio.gather(*(load(c.id) for c in campaigns))

        items = [self._to_item(c, lookups, streams_by_campaign.get(c.id)) for c in campaigns]
        items.sort(key=lambda i: i.id, reverse=True)
        offers_total = None
        if with_offers:
            offers_total = len(
                {o.offer_id for streams in streams_by_campaign.values() if streams for s in streams for o in s.offers}
            )
        return CampaignListResponse(items=items, total=len(items), offers_total=offers_total)

    async def get_detail(self, campaign_id: int) -> CampaignDetail:
        raw_campaign, raw_streams, raw_offers, lookups = await asyncio.gather(
            self.client.get_campaign(campaign_id),
            self.client.list_streams(campaign_id),
            _tolerant(self.client.list_offers(), [], "offers"),
            self._lookups(),
        )
        campaign = CampaignOut.model_validate(raw_campaign)
        streams = sort_streams([StreamOut.model_validate(s) for s in raw_streams])
        offer_names = _names(OfferOut.model_validate(o) for o in raw_offers)
        local = await self.repo.get_by_keitaro_id(campaign_id)
        return CampaignDetail(
            campaign=self._to_item(campaign, lookups, streams),
            streams=streams,
            offers=collect_offers(streams, offer_names),
            local=LocalCampaignInfo.model_validate(local) if local else None,
        )

    # ----------------------------------------------------------------- write
    async def create(self, data: CampaignCreate) -> CampaignDetail:
        try:
            await self.client.get_offer(data.offer_id)
        except KeitaroNotFoundError as exc:
            raise ValidationAppError(f"Оффер #{data.offer_id} не найден в Keitaro") from exc

        async with self.audit.track("campaign.create", details=data.model_dump()) as ctx:
            campaign_payload = {
                "name": data.name,
                "alias": generate_alias(),
                "type": "position",
                "state": "active",
                "group_id": data.group_id,
                "traffic_source_id": data.traffic_source_id,
                "domain_id": data.domain_id,
            }
            created = CampaignOut.model_validate(await self.client.create_campaign(campaign_payload))
            ctx["campaign_id"] = created.id

            try:
                geo_stream = await self.client.create_stream(self._geo_stream_payload(created.id, data.country))
                offer_stream = await self.client.create_stream(self._offer_stream_payload(created.id, data.offer_id))
            except KeitaroError:
                logger.warning("Stream creation failed, removing campaign %s", created.id)
                try:
                    await self.client.delete_campaign(created.id)
                except KeitaroError:
                    logger.exception("Rollback of campaign %s failed", created.id)
                raise

            await self.repo.create(
                keitaro_id=created.id,
                name=created.name,
                alias=created.alias,
                country=data.country,
                offer_id=data.offer_id,
                domain_id=data.domain_id,
                group_id=data.group_id,
                traffic_source_id=data.traffic_source_id,
                geo_stream_id=geo_stream.get("id"),
                offer_stream_id=offer_stream.get("id"),
            )
            await self.session.commit()
            ctx["message"] = f"Создана кампания «{created.name}» с двумя потоками"
        return await self.get_detail(created.id)

    def _geo_stream_payload(self, campaign_id: int, country: str) -> dict[str, Any]:
        return {
            "campaign_id": campaign_id,
            "type": "regular",
            "name": f"GEO {country} → {self.safe_url}",
            "position": 1,
            "state": "active",
            "schema": "redirect",
            "action_type": "http",
            "action_payload": self.safe_url,
            "collect_clicks": True,
            "filter_or": False,
            "filters": [{"name": "country", "mode": "accept", "payload": [country]}],
        }

    @staticmethod
    def _offer_stream_payload(campaign_id: int, offer_id: int) -> dict[str, Any]:
        return {
            "campaign_id": campaign_id,
            "type": "regular",
            "name": "Offers",
            "position": 2,
            "state": "active",
            "schema": "landings",
            "action_type": "http",
            "collect_clicks": True,
            "filter_or": False,
            "filters": [],
            "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
        }

    async def update(self, campaign_id: int, data: CampaignUpdate) -> CampaignDetail:
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        state = changes.pop("state", None)
        async with self.audit.track("campaign.update", campaign_id=campaign_id, details=data.model_dump(exclude_unset=True)):
            if changes:
                await self.client.update_campaign(campaign_id, changes)
            if state == "active":
                await self.client.enable_campaign(campaign_id)
            elif state == "disabled":
                await self.client.disable_campaign(campaign_id)
        return await self.get_detail(campaign_id)

    async def delete(self, campaign_id: int) -> None:
        async with self.audit.track("campaign.delete", campaign_id=campaign_id):
            await self.client.delete_campaign(campaign_id)
            await self.repo.mark_deleted(campaign_id)
            await self.session.commit()
