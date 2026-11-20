"""Audit trail for write operations (stored in campaign_logs)."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.campaign_log_repository import CampaignLogRepository

logger = logging.getLogger("app.audit")


class AuditLogger:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CampaignLogRepository(session)

    @asynccontextmanager
    async def track(
        self, action: str, *, campaign_id: int | None = None, details: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields a mutable context; set ``ctx["campaign_id"]`` / ``ctx["message"]`` inside the block."""
        ctx: dict[str, Any] = {"campaign_id": campaign_id, "message": None, "details": dict(details or {})}
        try:
            yield ctx
        except Exception as exc:
            await self.session.rollback()
            logger.warning("%s failed (campaign=%s): %s", action, ctx["campaign_id"], exc)
            await self._write(action, ctx, status="error", message=str(exc))
            raise
        else:
            logger.info("%s succeeded (campaign=%s)", action, ctx["campaign_id"])
            await self._write(action, ctx, status="success", message=ctx["message"])

    async def _write(self, action: str, ctx: dict[str, Any], *, status: str, message: str | None) -> None:
        try:
            await self.repo.add(
                action, campaign_keitaro_id=ctx["campaign_id"], status=status, message=message, details=ctx["details"]
            )
            await self.session.commit()
        except Exception:  # audit must never break the main operation
            logger.exception("Failed to write audit log for %s", action)
            await self.session.rollback()
