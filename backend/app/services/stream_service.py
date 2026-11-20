from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.keitaro.client import KeitaroClient
from app.schemas.keitaro import StreamOut
from app.schemas.stream import StreamIn
from app.services.audit import AuditLogger
from app.services.campaign_service import sort_streams


class StreamService:
    def __init__(self, client: KeitaroClient, session: AsyncSession) -> None:
        self.client = client
        self.audit = AuditLogger(session)

    async def list(self, campaign_id: int) -> list[StreamOut]:
        await self.client.get_campaign(campaign_id)
        return sort_streams([StreamOut.model_validate(s) for s in await self.client.list_streams(campaign_id)])

    async def create(self, campaign_id: int, data: StreamIn) -> StreamOut:
        existing = await self.list(campaign_id)
        payload = data.to_keitaro(campaign_id)
        if data.position is None:
            payload["position"] = max((s.position or 0 for s in existing), default=0) + 1
        async with self.audit.track("stream.create", campaign_id=campaign_id, details=payload) as ctx:
            created = StreamOut.model_validate(await self.client.create_stream(payload))
            ctx["message"] = f"Создан поток #{created.id}"
        return created

    async def get(self, stream_id: int) -> StreamOut:
        return StreamOut.model_validate(await self.client.get_stream(stream_id))

    async def update(self, stream_id: int, data: StreamIn) -> StreamOut:
        current = await self.get(stream_id)
        payload = data.to_keitaro(current.campaign_id)
        if data.position is None and current.position is not None:
            payload["position"] = current.position
        async with self.audit.track("stream.update", campaign_id=current.campaign_id, details=payload):
            updated = StreamOut.model_validate(await self.client.update_stream(stream_id, payload))
        return updated

    async def set_state(self, stream_id: int, enabled: bool) -> StreamOut:
        current = await self.get(stream_id)
        action = "stream.enable" if enabled else "stream.disable"
        async with self.audit.track(action, campaign_id=current.campaign_id, details={"stream_id": stream_id}):
            if enabled:
                await self.client.enable_stream(stream_id)
            else:
                await self.client.disable_stream(stream_id)
        return await self.get(stream_id)

    async def delete(self, stream_id: int) -> None:
        current = await self.get(stream_id)
        async with self.audit.track("stream.delete", campaign_id=current.campaign_id, details={"stream_id": stream_id}):
            await self.client.delete_stream(stream_id)
