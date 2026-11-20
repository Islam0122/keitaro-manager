from fastapi import APIRouter

from app.api.routers import campaigns, health, resources, settings, streams

api_router = APIRouter(prefix="/api")
for module in (health, campaigns, streams, resources, settings):
    api_router.include_router(module.router)
