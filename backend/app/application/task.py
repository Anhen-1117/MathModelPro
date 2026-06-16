"""TaskService — 任务生命周期管理"""

import uuid
import asyncio
from datetime import datetime
from typing import Optional

from app.domain import Task, TaskStatus, PhaseProgress
from app.domain.pipeline.engine import PipelineEngine
from app.infrastructure.repository import TaskRepository
from app.infrastructure.events import get_event_bus


class TaskService:
    """任务应用服务。组合 Repository + Pipeline + EventBus。"""

    def __init__(self, repo: TaskRepository):
        self.repo = repo
        self.events = get_event_bus()

    # ── CRUD ───────────────────────────────────────────

    def create(self, name: str, problem_text: str = "",
               description: str = "", language: str = "python",
               template_id: str = "cumcm", notes: str = "") -> Task:
        task = Task(
            id=uuid.uuid4().hex[:12],
            name=name,
            description=description,
            problem_text=problem_text,
            language=language,
            template_id=template_id,
            notes=notes,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return self.repo.create(task)

    def get(self, task_id: str) -> Task:
        return self.repo.get(task_id)

    def list(self, status: Optional[str] = None,
             limit: int = 20, offset: int = 0) -> list[Task]:
        return self.repo.list(status=status, limit=limit, offset=offset)

    def delete(self, task_id: str):
        self.repo.delete(task_id)

    # ── 工作流 ─────────────────────────────────────────

    async def start(self, task_id: str):
        """启动建模流水线（后台运行）"""
        task = self.repo.get(task_id)
        if task.status != TaskStatus.PENDING:
            from app.errors import TaskInvalidStateError
            raise TaskInvalidStateError(task_id, task.status.value, TaskStatus.PENDING.value)

        self.repo.update_status(task_id, TaskStatus.RUNNING)
        self.repo.update_agent_status(task_id, "coordinator", "running")

        engine = PipelineEngine()
        # 注册 EventBus 订阅者（实时推送进度到前端）
        await self._register_handlers(task_id)

        # 后台执行
        asyncio.create_task(self._run_pipeline(task_id, engine, task))

    async def _run_pipeline(self, task_id: str, engine: PipelineEngine, task: Task):
        try:
            result = await engine.run(task)
            self.repo.save_result(
                task_id,
                paper_content=result.get("paper_content"),
                code=result.get("code"),
                figures=result.get("figures"),
            )
        except Exception as e:
            self.repo.update_status(task_id, TaskStatus.FAILED)
            raise

    # ── EventBus 订阅 ───────────────────────────────────

    async def _register_handlers(self, task_id: str):
        """订阅进度和日志事件，同步写入数据库"""

        async def on_progress(event):
            data = event.data
            if "status" in data:
                self.repo.update_status(task_id, TaskStatus(data["status"]))
                return
            phase = data.get("phase", "")
            value = data.get("value", 0)
            self.repo.update_progress(task_id, PhaseProgress(
                **{phase: value, **{
                    p: 0 for p in ["analysis", "modeling", "coding", "paper"] if p != phase
                }}
            ))

        async def on_log(event):
            data = event.data
            agent = data.get("agent", "")
            self.repo.update_agent_status(task_id, agent, "running")

        await self.events.subscribe(f"task:{task_id}:progress", on_progress)
        await self.events.subscribe(f"task:{task_id}:messages", on_log)
