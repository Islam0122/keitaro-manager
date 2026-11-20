from app.integrations.keitaro.client import KeitaroClient
from app.schemas.keitaro import DomainOut, GroupOut, OfferOut, TrafficSourceOut


class ResourceService:
    def __init__(self, client: KeitaroClient) -> None:
        self.client = client

    async def domains(self) -> list[DomainOut]:
        return [DomainOut.model_validate(d) for d in await self.client.list_domains()]

    async def groups(self, group_type: str = "campaign") -> list[GroupOut]:
        return [GroupOut.model_validate(g) for g in await self.client.list_groups(group_type)]

    async def sources(self) -> list[TrafficSourceOut]:
        return [TrafficSourceOut.model_validate(s) for s in await self.client.list_traffic_sources()]

    async def offers(self) -> list[OfferOut]:
        return [OfferOut.model_validate(o) for o in await self.client.list_offers()]
