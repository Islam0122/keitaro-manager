from typing import Any

from sqlalchemy import select

from app.models import Campaign
from app.repositories.base import BaseRepository


class CampaignRepository(BaseRepository):
    async def get_by_keitaro_id(self, keitaro_id: int) -> Campaign | None:
        result = await self.session.execute(select(Campaign).where(Campaign.keitaro_id == keitaro_id))
        return result.scalar_one_or_none()

    async def create(self, **fields: Any) -> Campaign:
        campaign = Campaign(**fields)
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def mark_deleted(self, keitaro_id: int) -> None:
        campaign = await self.get_by_keitaro_id(keitaro_id)
        if campaign:
            campaign.is_deleted = True
            await self.session.flush()
