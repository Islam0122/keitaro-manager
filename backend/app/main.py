import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import register_secret, setup_logging

settings = get_settings()
setup_logging(settings.log_level)
register_secret(settings.keitaro_api_key)
register_secret(settings.admin_password)
logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.admin_username and settings.admin_password:
        from app.db.session import SessionLocal
        from app.services.auth_service import AuthService

        try:
            async with SessionLocal() as session:
                await AuthService(session).ensure_bootstrap_admin()
        except Exception:
            logger.exception("Could not create the bootstrap admin user")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="REST API для управления рекламными кампаниями через Keitaro Admin API.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # auth uses the Authorization header, not cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - started) * 1000
    logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed)
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


register_exception_handlers(app)
app.include_router(api_router)
