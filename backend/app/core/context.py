"""Per-request context (set by the auth dependency, read by the audit logger)."""
from contextvars import ContextVar

current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
