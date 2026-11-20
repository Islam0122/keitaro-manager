"""Application level exceptions and FastAPI handlers."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.security import SecretDecryptionError
from app.integrations.keitaro.exceptions import (
    KeitaroAPIError,
    KeitaroAuthError,
    KeitaroConnectionError,
    KeitaroError,
    KeitaroNotConfiguredError,
    KeitaroNotFoundError,
    KeitaroTimeoutError,
)

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
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


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": message, "code": code})


_KEITARO_STATUS: list[tuple[type[KeitaroError], int, str]] = [
    (KeitaroNotConfiguredError, 400, "keitaro_not_configured"),
    (KeitaroAuthError, 502, "keitaro_auth_failed"),
    (KeitaroNotFoundError, 404, "keitaro_not_found"),
    (KeitaroTimeoutError, 504, "keitaro_timeout"),
    (KeitaroConnectionError, 502, "keitaro_unavailable"),
]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

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
        for cls, status, code in _KEITARO_STATUS:
            if isinstance(exc, cls):
                return _error(status, code, str(exc))
        if isinstance(exc, KeitaroAPIError) and exc.status_code and 400 <= exc.status_code < 500:
            return _error(422, "keitaro_rejected", str(exc))
        return _error(502, "keitaro_error", str(exc))

    @app.exception_handler(SecretDecryptionError)
    async def _secret_error(_: Request, exc: SecretDecryptionError) -> JSONResponse:
        return _error(500, "secret_decryption_failed", str(exc))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "internal_error", "Внутренняя ошибка сервера")
