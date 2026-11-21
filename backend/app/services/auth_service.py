"""Login with brute-force protection, token issuing and user management."""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, TooManyAttemptsError, ValidationAppError
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, hash_password, verify_password
from app.models import User
from app.repositories.user_repository import LoginAttemptRepository, UserRepository
from app.schemas.auth import TokenOut, UserOut, check_password_strength

logger = logging.getLogger("app.auth")

# An IP may fail this many times more than a single username before it is blocked (several operators behind one NAT).
IP_ATTEMPTS_FACTOR = 4


def normalize_username(value: str) -> str:
    return value.strip().lower()


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.attempts = LoginAttemptRepository(session)

    async def _check_lockout(self, username: str, ip: str) -> None:
        settings = get_settings()
        now = datetime.now(UTC)
        lockout = timedelta(minutes=settings.login_lockout_minutes)
        window_start = now - lockout
        last_success = _aware(await self.attempts.last_success_at(username))
        user_since = max(window_start, last_success) if last_success else window_start

        user_failures = await self.attempts.failures_since(user_since, username=username)
        ip_failures = await self.attempts.failures_since(window_start, ip=ip)
        blocked_by: dict[str, str] | None = None
        if user_failures >= settings.login_max_attempts:
            blocked_by = {"username": username}
        elif ip_failures >= settings.login_max_attempts * IP_ATTEMPTS_FACTOR:
            blocked_by = {"ip": ip}
        if blocked_by is None:
            return
        since = user_since if "username" in blocked_by else window_start
        oldest = _aware(await self.attempts.oldest_failure_since(since, **blocked_by))
        retry_after = max(1, int(((oldest or now) + lockout - now).total_seconds()))
        logger.warning("Login blocked for %s (ip=%s), retry in %ss", username, ip, retry_after)
        raise TooManyAttemptsError(
            f"Слишком много неудачных попыток входа. Повторите через {retry_after // 60 + 1} мин.",
            headers={"Retry-After": str(retry_after)},
            extra={"retry_after": retry_after},
        )

    async def login(self, username: str, password: str, ip: str) -> TokenOut:
        username = normalize_username(username)
        await self._check_lockout(username, ip)

        user = await self.users.get_by_username(username)
        # Always run the hash function so that response time does not reveal whether the user exists.
        password_ok = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
        success = bool(user and user.is_active and password_ok)

        await self.attempts.add(username, ip, success)
        if success and user:
            user.last_login_at = datetime.now(UTC)
        await self.session.commit()

        if not success or user is None:
            logger.info("Failed login for %s from %s", username, ip)
            raise AuthenticationError("Неверный логин или пароль", code="invalid_credentials")
        token, expires = create_access_token(user.id, user.username)
        logger.info("User %s logged in from %s", username, ip)
        return TokenOut(access_token=token, expires_at=expires, user=UserOut.model_validate(user))

    async def create_user(self, username: str, password: str) -> User:
        username = normalize_username(username)
        if await self.users.get_by_username(username):
            raise ValidationAppError(f"Пользователь {username} уже существует")
        user = await self.users.create(username, hash_password(password))
        await self.session.commit()
        return user

    async def set_password(self, user: User, password: str) -> None:
        user.password_hash = hash_password(password)
        await self.session.commit()

    async def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise ValidationAppError(
                "Текущий пароль указан неверно",
                errors=[{"field": "current_password", "message": "Текущий пароль указан неверно"}],
            )
        await self.set_password(user, new)

    async def ensure_bootstrap_admin(self) -> None:
        settings = get_settings()
        if not (settings.admin_username and settings.admin_password):
            return
        username = normalize_username(settings.admin_username)
        try:
            check_password_strength(settings.admin_password)
        except ValueError as exc:
            logger.error("ADMIN_PASSWORD is too weak, bootstrap admin not created: %s", exc)
            return
        if await self.users.get_by_username(username):
            return
        await self.users.create(username, hash_password(settings.admin_password))
        await self.session.commit()
        logger.info("Bootstrap admin user %s created", username)
