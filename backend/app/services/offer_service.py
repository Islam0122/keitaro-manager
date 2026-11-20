"""Management of offers inside campaign streams (Keitaro stream ``offers`` field)."""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.integrations.keitaro.client import KeitaroClient
from app.integrations.keitaro.exceptions import KeitaroNotFoundError
from app.schemas.keitaro import OfferOut, StreamOfferOut, StreamOut
from app.schemas.offer import CampaignOfferAdd, CampaignOffersResponse, CampaignOffersUpdate, OfferStreamSummary
from app.services.audit import AuditLogger
from app.services.campaign_service import _names, _tolerant, collect_offers, sort_streams
from app.services.distribution import equal_split, scale_to_total


def offer_streams(streams: list[StreamOut]) -> list[StreamOut]:
    return [s for s in streams if s.schema_ == "landings"]


def _serialize(offers: list[StreamOfferOut]) -> list[dict]:
    return [{"offer_id": o.offer_id, "share": o.share, "state": o.state} for o in offers]


def rebalance(offers: list[StreamOfferOut], fixed: dict[int, int] | None = None) -> list[StreamOfferOut]:
    """Rescale active offers to 100%. ``fixed`` pins shares of given offer ids (the rest share the remainder)."""
    fixed = fixed or {}
    active = [o for o in offers if o.state == "active"]
    free = [o for o in active if o.offer_id not in fixed]
    remainder = 100 - sum(fixed.get(o.offer_id, 0) for o in active)
    if not free:
        remainder = 0
    for offer in active:
        if offer.offer_id in fixed:
            offer.share = fixed[offer.offer_id] if free else 100
    for offer, share in zip(free, scale_to_total([o.share for o in free], remainder), strict=True):
        offer.share = share
    return offers


class OfferService:
    def __init__(self, client: KeitaroClient, session: AsyncSession) -> None:
        self.client = client
        self.audit = AuditLogger(session)

    async def _streams(self, campaign_id: int) -> list[StreamOut]:
        await self.client.get_campaign(campaign_id)  # raises 404 if campaign does not exist
        return sort_streams([StreamOut.model_validate(s) for s in await self.client.list_streams(campaign_id)])

    @staticmethod
    def _pick_stream(streams: list[StreamOut], stream_id: int | None) -> StreamOut:
        candidates = offer_streams(streams)
        if stream_id is not None:
            for stream in streams:
                if stream.id == stream_id:
                    if stream.schema_ != "landings":
                        raise ValidationAppError("В выбранном потоке схема не поддерживает офферы")
                    return stream
            raise NotFoundError(f"Поток #{stream_id} не принадлежит кампании")
        if not candidates:
            raise ValidationAppError("В кампании нет потока с офферами. Создайте поток со схемой «Офферы».")
        with_offers = [s for s in candidates if s.offers]
        return (with_offers or candidates)[0]

    async def list(self, campaign_id: int) -> CampaignOffersResponse:
        streams, raw_offers = await asyncio.gather(
            self._streams(campaign_id), _tolerant(self.client.list_offers(), [], "offers")
        )
        names = _names(OfferOut.model_validate(o) for o in raw_offers)
        summaries = [
            OfferStreamSummary(
                stream_id=s.id,
                name=s.name,
                state=s.state,
                total_share=sum(o.share for o in s.offers if o.state == "active"),
                offers_count=len(s.offers),
            )
            for s in offer_streams(streams)
        ]
        return CampaignOffersResponse(campaign_id=campaign_id, items=collect_offers(streams, names), streams=summaries)

    async def add(self, campaign_id: int, data: CampaignOfferAdd) -> CampaignOffersResponse:
        stream = self._pick_stream(await self._streams(campaign_id), data.stream_id)
        if any(o.offer_id == data.offer_id for o in stream.offers):
            raise ValidationAppError(f"Оффер #{data.offer_id} уже есть в потоке «{stream.name}»")
        try:
            await self.client.get_offer(data.offer_id)
        except KeitaroNotFoundError as exc:
            raise ValidationAppError(f"Оффер #{data.offer_id} не найден в Keitaro") from exc

        offers = [*stream.offers, StreamOfferOut(offer_id=data.offer_id, share=0, state="active")]
        if data.share is None:
            active = [o for o in offers if o.state == "active"]
            for offer, share in zip(active, equal_split(len(active)), strict=True):
                offer.share = share
        else:
            rebalance(offers, fixed={data.offer_id: data.share})

        async with self.audit.track(
            "offer.add", campaign_id=campaign_id, details={"stream_id": stream.id, "offer_id": data.offer_id}
        ):
            await self.client.update_stream(stream.id, {"offers": _serialize(offers)})
        return await self.list(campaign_id)

    async def update(self, campaign_id: int, data: CampaignOffersUpdate) -> CampaignOffersResponse:
        stream = self._pick_stream(await self._streams(campaign_id), data.stream_id)
        offers = [o.model_dump() for o in data.offers]
        async with self.audit.track("offer.update", campaign_id=campaign_id, details={"stream_id": stream.id, "offers": offers}):
            await self.client.update_stream(stream.id, {"offers": offers})
        return await self.list(campaign_id)

    async def remove(self, campaign_id: int, offer_id: int, stream_id: int | None = None) -> CampaignOffersResponse:
        streams = await self._streams(campaign_id)
        targets = [
            s
            for s in offer_streams(streams)
            if (stream_id is None or s.id == stream_id) and any(o.offer_id == offer_id for o in s.offers)
        ]
        if not targets:
            raise NotFoundError(f"Оффер #{offer_id} не найден в потоках кампании")
        updates: list[tuple[StreamOut, list[StreamOfferOut]]] = []
        for stream in targets:
            remaining = [o for o in stream.offers if o.offer_id != offer_id]
            if not remaining:
                raise ValidationAppError(
                    f"Нельзя удалить последний оффер потока «{stream.name}». Добавьте другой оффер или удалите поток."
                )
            if not any(o.state == "active" for o in remaining):
                raise ValidationAppError(f"В потоке «{stream.name}» не останется активных офферов")
            updates.append((stream, rebalance(remaining)))

        async with self.audit.track(
            "offer.remove", campaign_id=campaign_id, details={"offer_id": offer_id, "streams": [s.id for s in targets]}
        ):
            for stream, remaining in updates:
                await self.client.update_stream(stream.id, {"offers": _serialize(remaining)})
        return await self.list(campaign_id)
