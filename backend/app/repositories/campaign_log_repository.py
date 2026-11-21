from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.context import current_user_id
from app.models import CampaignLog
from app.repositories.base import BaseRepository


class CampaignLogRepository(BaseRepository):
    async def add(
        self,
        action: str,
        *,
        campaign_keitaro_id: int | None = None,
        status: str = "success",
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> CampaignLog:
        log = CampaignLog(
            action=action,
            campaign_keitaro_id=campaign_keitaro_id,
            status=status,
            message=message,
            details=details,
            user_id=current_user_id.get(),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list(self, *, campaign_keitaro_id: int | None = None, limit: int = 100) -> Sequence[CampaignLog]:
        query = (
            select(CampaignLog)
            .options(selectinload(CampaignLog.user))
            .order_by(CampaignLog.created_at.desc(), CampaignLog.id.desc())
            .limit(limit)
        )
        if campaign_keitaro_id is not None:
            query = query.where(CampaignLog.campaign_keitaro_id == campaign_keitaro_id)
        result = await self.session.execute(query)
        return result.scalars().all()
