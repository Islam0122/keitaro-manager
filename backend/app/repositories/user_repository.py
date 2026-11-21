from datetime import datetime

from sqlalchemy import func, select

from app.models import LoginAttempt, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, username: str, password_hash: str) -> User:
        user = User(username=username, password_hash=password_hash, is_active=True)
        self.session.add(user)
        await self.session.flush()
        return user


class LoginAttemptRepository(BaseRepository):
    async def add(self, username: str, ip: str, success: bool) -> None:
        self.session.add(LoginAttempt(username=username, ip=ip, success=success))
        await self.session.flush()

    async def last_success_at(self, username: str) -> datetime | None:
        result = await self.session.execute(
            select(func.max(LoginAttempt.created_at)).where(
                LoginAttempt.username == username, LoginAttempt.success.is_(True)
            )
        )
        return result.scalar_one_or_none()

    async def failures_since(self, since: datetime, *, username: str | None = None, ip: str | None = None) -> int:
        query = select(func.count(LoginAttempt.id)).where(
            LoginAttempt.success.is_(False), LoginAttempt.created_at >= since
        )
        if username is not None:
            query = query.where(LoginAttempt.username == username)
        if ip is not None:
            query = query.where(LoginAttempt.ip == ip)
        result = await self.session.execute(query)
        return int(result.scalar_one())

    async def oldest_failure_since(
        self, since: datetime, *, username: str | None = None, ip: str | None = None
    ) -> datetime | None:
        query = select(func.min(LoginAttempt.created_at)).where(
            LoginAttempt.success.is_(False), LoginAttempt.created_at >= since
        )
        if username is not None:
            query = query.where(LoginAttempt.username == username)
        if ip is not None:
            query = query.where(LoginAttempt.ip == ip)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
