"""任务数据仓储 — 封装所有 SQLAlchemy 操作"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.domain import Task, TaskStatus, PhaseProgress
from app.errors import TaskNotFoundError

# 临时直接从旧 models 导入，后续 Phase 3 迁移到 infrastructure 内部
from app.models.database import TaskDB, SessionLocal


class TaskRepository:
    """任务数据访问层。封装所有 SessionLocal 操作。"""

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_session = db is None

    def _session(self) -> Session:
        if self._db is not None:
            return self._db
        return SessionLocal()

    def _close(self, db: Session):
        if self._owns_session:
            db.close()

    # ── CRUD ───────────────────────────────────────────

    def create(self, task: Task) -> Task:
        db = self._session()
        try:
            record = TaskDB(
                id=task.id,
                name=task.name,
                description=task.description,
                problem_text=task.problem_text,
                language=task.language,
                template_id=task.template_id,
                notes=task.notes,
                status=task.status.value,
                created_at=task.created_at or datetime.now(),
                updated_at=task.updated_at or datetime.now(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_domain(record)
        finally:
            self._close(db)

    def get(self, task_id: str) -> Task:
        db = self._session()
        try:
            record = db.query(TaskDB).filter(TaskDB.id == task_id).first()
            if not record:
                raise TaskNotFoundError(task_id)
            return self._to_domain(record)
        finally:
            self._close(db)

    def list(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Task]:
        db = self._session()
        try:
            q = db.query(TaskDB).order_by(TaskDB.created_at.desc())
            if status:
                q = q.filter(TaskDB.status == status)
            records = q.offset(offset).limit(limit).all()
            return [self._to_domain(r) for r in records]
        finally:
            self._close(db)

    def count(self, status: Optional[str] = None) -> int:
        db = self._session()
        try:
            q = db.query(TaskDB)
            if status:
                q = q.filter(TaskDB.status == status)
            return q.count()
        finally:
            self._close(db)

    # ── 更新 ───────────────────────────────────────────

    def update_status(self, task_id: str, status: TaskStatus):
        db = self._session()
        try:
            record = db.query(TaskDB).filter(TaskDB.id == task_id).first()
            if not record:
                raise TaskNotFoundError(task_id)
            record.status = status.value
            record.updated_at = datetime.now()
            db.commit()
        finally:
            self._close(db)

    def update_progress(self, task_id: str, progress: PhaseProgress):
        db = self._session()
        try:
            record = db.query(TaskDB).filter(TaskDB.id == task_id).first()
            if not record:
                raise TaskNotFoundError(task_id)
            record.progress = {
                "analysis": progress.analysis,
                "modeling": progress.modeling,
                "coding": progress.coding,
                "paper": progress.paper,
                "overall": progress.overall,
            }
            record.updated_at = datetime.now()
            db.commit()
        finally:
            self._close(db)

    def update_agent_status(self, task_id: str, agent: str, status: str):
        db = self._session()
        try:
            record = db.query(TaskDB).filter(TaskDB.id == task_id).first()
            if not record:
                raise TaskNotFoundError(task_id)
            agent_status = dict(record.agent_status) if record.agent_status else {}
            agent_status[agent] = status
            record.agent_status = agent_status
            record.updated_at = datetime.now()
            db.commit()
        finally:
            self._close(db)

    def save_result(
        self,
        task_id: str,
        *,
        paper_content: Optional[str] = None,
        code: Optional[str] = None,
        figures: Optional[list] = None,
    ):
        db = self._session()
        try:
            record = db.query(TaskDB).filter(TaskDB.id == task_id).first()
            if not record:
                raise TaskNotFoundError(task_id)
            if paper_content is not None:
                record.paper_content = paper_content
            if code is not None:
                record.code = code
            if figures is not None:
                record.figures = figures
            record.updated_at = datetime.now()
            record.completed_at = datetime.now()
            record.status = TaskStatus.COMPLETED.value
            db.commit()
        finally:
            self._close(db)

    def delete(self, task_id: str):
        db = self._session()
        try:
            record = db.query(TaskDB).filter(TaskDB.id == task_id).first()
            if not record:
                raise TaskNotFoundError(task_id)
            db.delete(record)
            db.commit()
        finally:
            self._close(db)

    # ── 转换 ───────────────────────────────────────────

    @staticmethod
    def _to_domain(record: TaskDB) -> Task:
        prog = record.progress or {}
        return Task(
            id=record.id,
            name=record.name,
            description=record.description or "",
            problem_text=record.problem_text or "",
            language=record.language or "python",
            template_id=record.template_id or "cumcm",
            status=TaskStatus(record.status),
            progress=PhaseProgress(
                analysis=prog.get("analysis", 0),
                modeling=prog.get("modeling", 0),
                coding=prog.get("coding", 0),
                paper=prog.get("paper", 0),
            ),
            agent_status=dict(record.agent_status) if record.agent_status else {},
            paper_content=record.paper_content,
            code=record.code,
            notes=record.notes or "",
            figures=list(record.figures) if record.figures else [],
            created_at=record.created_at,
            updated_at=record.updated_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )
