"""任务 API（V2）— 薄路由，委托给 TaskService"""

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_task_service, get_task_repo
from app.application.task import TaskService
from app.infrastructure.repository import TaskRepository
from app.schemas import CreateTaskRequest, TaskResponse, TaskListResponse
from app.errors import TaskNotFoundError, TaskInvalidStateError

router = APIRouter()


@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    request: CreateTaskRequest,
    svc: TaskService = Depends(get_task_service),
):
    """创建数学建模任务"""
    task = svc.create(
        name=request.name,
        problem_text=request.problem_text,
        description=request.description,
        language=request.language,
        template_id=request.template_id,
        notes=request.notes,
    )
    return _to_response(task)


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    svc: TaskService = Depends(get_task_service),
    repo: TaskRepository = Depends(get_task_repo),
):
    """获取任务列表"""
    tasks = svc.list(status=status, limit=limit, offset=offset)
    total = repo.count(status=status)
    return TaskListResponse(
        tasks=[_to_response(t) for t in tasks],
        total=total,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    svc: TaskService = Depends(get_task_service),
):
    """获取任务详情"""
    try:
        task = svc.get(task_id)
        return _to_response(task)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: str,
    svc: TaskService = Depends(get_task_service),
):
    """启动建模工作流"""
    try:
        await svc.start(task_id)
        return {"status": "running", "task_id": task_id}
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except TaskInvalidStateError as e:
        raise HTTPException(status_code=409, detail=e.message)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    svc: TaskService = Depends(get_task_service),
):
    """删除任务"""
    try:
        svc.delete(task_id)
        return {"status": "deleted"}
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


# ── 辅助 ──────────────────────────────────────────────

def _to_response(task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description or "",
        problem_text=task.problem_text or "",
        language=task.language or "python",
        template_id=task.template_id or "cumcm",
        status=task.status.value if hasattr(task.status, 'value') else str(task.status),
        progress={
            "analysis": task.progress.analysis,
            "modeling": task.progress.modeling,
            "coding": task.progress.coding,
            "paper": task.progress.paper,
            "overall": task.progress.overall,
        },
        agent_status=task.agent_status or {},
        paper_content=task.paper_content,
        code=task.code,
        notes=getattr(task, 'notes', '') or '',
        figures=task.figures or [],
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )
