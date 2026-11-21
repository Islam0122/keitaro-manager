"""Application level exceptions and FastAPI handlers."""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.security import SecretDecryptionError
from app.core.url_guard import UnsafeURLError
from app.integrations.keitaro.exceptions import (
    KeitaroAPIError,
    KeitaroAuthError,
    KeitaroConnectionError,
    KeitaroError,
    KeitaroNotConfiguredError,
    KeitaroNotFoundError,
    KeitaroRateLimitError,
    KeitaroServerError,
    KeitaroTimeoutError,
    KeitaroValidationError,
)

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.extra = extra or {}
        self.headers = headers
        if status_code:
            self.status_code = status_code
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"

    def __init__(self, message: str, *, errors: list[dict[str, str]] | None = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        if errors:
            self.extra["errors"] = errors


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"

    def __init__(self, message: str = "Требуется авторизация", **kwargs: Any):
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kwargs)


class TooManyAttemptsError(AppError):
    status_code = 429
    code = "too_many_attempts"


class OperationFailedError(AppError):
    """A multi-step Keitaro operation failed; ``extra['rollback']`` describes the compensation result."""

    status_code = 502
    code = "operation_failed"


def keitaro_status(exc: KeitaroError) -> tuple[int, str]:
    for cls, status, code in _KEITARO_STATUS:
        if isinstance(exc, cls):
            return status, code
    if isinstance(exc, KeitaroAPIError) and exc.status_code and 400 <= exc.status_code < 500:
        return 422, "keitaro_rejected"
    return 502, "keitaro_error"


def _error(
    status: int, code: str, message: str, extra: dict[str, Any] | None = None, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": message, "code": code, **(extra or {})}, headers=headers)


# Keitaro auth problems are reported as 502 (bad gateway), never 401: a 401 from *our* API means
# "your Keitaro Manager session expired", and the frontend logs the user out on it.
_KEITARO_STATUS: list[tuple[type[KeitaroError], int, str]] = [
    (KeitaroNotConfiguredError, 400, "keitaro_not_configured"),
    (KeitaroAuthError, 502, "keitaro_auth_failed"),
    (KeitaroNotFoundError, 404, "keitaro_not_found"),
    (KeitaroValidationError, 422, "keitaro_rejected"),
    (KeitaroRateLimitError, 429, "keitaro_rate_limited"),
    (KeitaroServerError, 502, "keitaro_server_error"),
    (KeitaroTimeoutError, 504, "keitaro_timeout"),
    (KeitaroConnectionError, 502, "keitaro_unavailable"),
]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.extra, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            field = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path"))
            message = str(err.get("msg", "")).removeprefix("Value error, ")
            errors.append({"field": field, "message": message})
        summary = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
        return JSONResponse(
            status_code=422,
            content={"detail": summary or "Некорректные данные", "code": "validation_error", "errors": errors},
        )

    @app.exception_handler(KeitaroError)
    async def _keitaro_error(request: Request, exc: KeitaroError) -> JSONResponse:
        logger.warning("Keitaro error on %s %s: %s", request.method, request.url.path, exc)
        status, code = keitaro_status(exc)
        headers = None
        if isinstance(exc, KeitaroRateLimitError) and exc.retry_after is not None:
            headers = {"Retry-After": str(int(exc.retry_after))}
        return _error(status, code, str(exc), headers=headers)

    @app.exception_handler(UnsafeURLError)
    async def _unsafe_url(_: Request, exc: UnsafeURLError) -> JSONResponse:
        return _error(422, "unsafe_url", str(exc), {"errors": [{"field": "api_url", "message": str(exc)}]})

    @app.exception_handler(SecretDecryptionError)
    async def _secret_error(_: Request, exc: SecretDecryptionError) -> JSONResponse:
        return _error(500, "secret_decryption_failed", str(exc))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "internal_error", "Внутренняя ошибка сервера")
