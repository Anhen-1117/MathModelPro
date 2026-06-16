"""FastAPI 依赖注入工厂"""

from app.infrastructure.repository import TaskRepository
from app.application.task import TaskService
from app.application.config import ConfigService


# ── 仓储 ──────────────────────────────────────────────

def get_task_repo() -> TaskRepository:
    return TaskRepository()


# ── 服务 ──────────────────────────────────────────────

def get_task_service() -> TaskService:
    return TaskService(repo=get_task_repo())


def get_config_service() -> ConfigService:
    return ConfigService()
