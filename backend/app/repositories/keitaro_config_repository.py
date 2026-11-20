from typing import Any

from sqlalchemy import select

from app.models import KeitaroConfig
from app.repositories.base import BaseRepository


class KeitaroConfigRepository(BaseRepository):
    async def get(self) -> KeitaroConfig | None:
        result = await self.session.execute(select(KeitaroConfig).order_by(KeitaroConfig.id).limit(1))
        return result.scalar_one_or_none()

    async def upsert(self, **fields: Any) -> KeitaroConfig:
        config = await self.get()
        if config is None:
            config = KeitaroConfig(**fields)
            self.session.add(config)
        else:
            for key, value in fields.items():
                setattr(config, key, value)
        await self.session.flush()
        return config
