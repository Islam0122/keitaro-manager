"""Management of offers inside campaign streams (Keitaro stream ``offers`` field).

Invariant enforced before every write: a stream with offers has at least one *active* offer and the shares of all
active offers sum to exactly 100. Disabled offers keep their share value but receive no traffic.
"""
import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, OperationFailedError, ValidationAppError, keitaro_status
from app.integrations.keitaro.client import KeitaroClient
from app.integrations.keitaro.exceptions import KeitaroError, KeitaroNotFoundError
from app.schemas.keitaro import OfferOut, StreamOfferOut, StreamOut
from app.schemas.offer import (
    CampaignOfferAdd,
    CampaignOffersResponse,
    CampaignOffersUpdate,
    OfferDistributeIn,
    OfferStreamSummary,
)
from app.services.audit import AuditLogger
from app.services.campaign_service import _names, _tolerant, collect_offers, sort_streams
from app.services.distribution import equal_split, scale_to_total

logger = logging.getLogger(__name__)


def offer_streams(streams: list[StreamOut]) -> list[StreamOut]:
    return [s for s in streams if s.schema_ == "landings"]


def _serialize(offers: list[StreamOfferOut]) -> list[dict[str, Any]]:
    return [{"offer_id": o.offer_id, "share": o.share, "state": o.state} for o in offers]


def _copy(offers: list[StreamOfferOut]) -> list[StreamOfferOut]:
    return [o.model_copy() for o in offers]


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


def distribute(offers: list[StreamOfferOut], mode: str) -> list[StreamOfferOut]:
    active = [o for o in offers if o.state == "active"]
    if not active:
        raise ValidationAppError("В потоке нет активных офферов для распределения")
    shares = equal_split(len(active)) if mode == "equal" else scale_to_total([o.share for o in active])
    for offer, share in zip(active, shares, strict=True):
        offer.share = share
    return offers


def check_invariant(stream: StreamOut, offers: list[StreamOfferOut]) -> None:
    active = [o for o in offers if o.state == "active"]
    if offers and not active:
        raise ValidationAppError(f"В потоке «{stream.name}» не останется активных офферов")
    total = sum(o.share for o in active)
    if active and total != 100:  # defensive: every code path should already produce 100
        raise ValidationAppError(f"Сумма долей активных офферов потока «{stream.name}» = {total}%, а должна быть 100%")


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

    async def _ensure_offers_exist(self, offer_ids: set[int]) -> None:
        if not offer_ids:
            return
        catalog = {OfferOut.model_validate(o).id for o in await self.client.list_offers()}
        missing = sorted(offer_ids - catalog)
        if missing:
            raise ValidationAppError(
                "Офферы не найдены в Keitaro: " + ", ".join(f"#{i}" for i in missing),
                errors=[{"field": "offers", "message": f"Оффер #{i} не найден в Keitaro"} for i in missing],
            )

    async def _apply(
        self, campaign_id: int, action: str, updates: list[tuple[StreamOut, list[StreamOfferOut]]], details: dict
    ) -> None:
        """Write new offer lists stream by stream; on failure restore the streams that were already changed."""
        for stream, offers in updates:
            check_invariant(stream, offers)
        async with self.audit.track(action, campaign_id=campaign_id, details=details) as ctx:
            done: list[StreamOut] = []
            try:
                for stream, offers in updates:
                    await self.client.update_stream(stream.id, {"offers": _serialize(offers)})
                    done.append(stream)
            except KeitaroError as exc:
                if not done:
                    raise
                rollback = await self._restore(done)
                ctx["details"]["rollback"] = rollback
                status, _code = keitaro_status(exc)
                suffix = (
                    "Изменённые потоки восстановлены."
                    if rollback["ok"]
                    else "Не удалось восстановить потоки: "
                    + ", ".join(f"#{s['id']}" for s in rollback["steps"] if not s["ok"])
                    + " — проверьте их вручную."
                )
                raise OperationFailedError(
                    f"Изменение применено частично и отменено: {exc}. {suffix}",
                    status_code=status,
                    code="partial_update_failed",
                    extra={"rollback": rollback},
                ) from exc

    async def _restore(self, streams: list[StreamOut]) -> dict[str, Any]:
        steps = []
        for stream in reversed(streams):
            try:
                await self.client.update_stream(stream.id, {"offers": _serialize(stream.offers)})
                steps.append({"object": "stream", "id": stream.id, "ok": True})
            except KeitaroError as err:
                logger.error("Rollback of stream %s failed: %s", stream.id, err)
                steps.append({"object": "stream", "id": stream.id, "ok": False, "error": str(err)})
        return {"performed": True, "ok": all(s["ok"] for s in steps), "steps": steps}

    # ----------------------------------------------------------------- reads
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

    # ---------------------------------------------------------------- writes
    async def add(self, campaign_id: int, data: CampaignOfferAdd) -> CampaignOffersResponse:
        stream = self._pick_stream(await self._streams(campaign_id), data.stream_id)
        if any(o.offer_id == data.offer_id for o in stream.offers):
            raise ConflictError(f"Оффер #{data.offer_id} уже есть в потоке «{stream.name}»", code="duplicate_offer")
        try:
            await self.client.get_offer(data.offer_id)
        except KeitaroNotFoundError as exc:
            raise ValidationAppError(f"Оффер #{data.offer_id} не найден в Keitaro") from exc

        offers = [*_copy(stream.offers), StreamOfferOut(offer_id=data.offer_id, share=0, state="active")]
        if data.share is None:
            distribute(offers, "equal")
        else:
            rebalance(offers, fixed={data.offer_id: data.share})
        await self._apply(
            campaign_id, "offer.add", [(stream, offers)], {"stream_id": stream.id, "offer_id": data.offer_id}
        )
        return await self.list(campaign_id)

    async def update(self, campaign_id: int, data: CampaignOffersUpdate) -> CampaignOffersResponse:
        stream = self._pick_stream(await self._streams(campaign_id), data.stream_id)
        current_ids = sorted(o.offer_id for o in stream.offers)
        if data.expected_offer_ids is not None and sorted(data.expected_offer_ids) != current_ids:
            raise ConflictError(
                "Поток изменился, пока вы его редактировали. Обновите страницу и повторите.", code="stale_stream"
            )
        await self._ensure_offers_exist({o.offer_id for o in data.offers} - set(current_ids))
        offers = [StreamOfferOut(**o.model_dump()) for o in data.offers]
        await self._apply(
            campaign_id,
            "offer.update",
            [(stream, offers)],
            {"stream_id": stream.id, "offers": _serialize(offers)},
        )
        return await self.list(campaign_id)

    async def distribute(self, campaign_id: int, data: OfferDistributeIn) -> CampaignOffersResponse:
        stream = self._pick_stream(await self._streams(campaign_id), data.stream_id)
        if not stream.offers:
            raise ValidationAppError("В потоке нет офферов")
        offers = distribute(_copy(stream.offers), data.mode)
        await self._apply(
            campaign_id, "offer.distribute", [(stream, offers)], {"stream_id": stream.id, "mode": data.mode}
        )
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
            remaining = [o for o in _copy(stream.offers) if o.offer_id != offer_id]
            if not remaining:
                raise ValidationAppError(
                    f"Нельзя удалить последний оффер потока «{stream.name}». Добавьте другой оффер или удалите поток."
                )
            if not any(o.state == "active" for o in remaining):
                raise ValidationAppError(f"В потоке «{stream.name}» не останется активных офферов")
            updates.append((stream, rebalance(remaining)))

        await self._apply(
            campaign_id, "offer.remove", updates, {"offer_id": offer_id, "streams": [s.id for s in targets]}
        )
        return await self.list(campaign_id)
