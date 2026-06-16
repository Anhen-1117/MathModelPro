"""V2 API 路由聚合 — 基于新架构的薄路由"""

from fastapi import APIRouter

from app.api.tasks_v2 import router as tasks_router
from app.api.settings_v2 import router as settings_router

v2_router = APIRouter(prefix="/api/v2")
v2_router.include_router(tasks_router, tags=["tasks"])
v2_router.include_router(settings_router, tags=["settings"])
