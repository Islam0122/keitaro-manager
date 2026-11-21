from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.routers import auth, campaigns, health, resources, settings, streams

api_router = APIRouter(prefix="/api")
# Public endpoints
api_router.include_router(health.router)
api_router.include_router(auth.router)
# Everything else requires a valid access token
for module in (campaigns, streams, resources, settings):
    api_router.include_router(module.router, dependencies=[Depends(get_current_user)])
