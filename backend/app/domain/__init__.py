"""领域类型 — 纯 Python，零外部依赖"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ── 任务 ──────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentName(str, Enum):
    COORDINATOR = "coordinator"
    MODELER = "modeler"
    CODER = "coder"
    WRITER = "writer"


@dataclass
class PhaseProgress:
    analysis: float = 0.0
    modeling: float = 0.0
    coding: float = 0.0
    paper: float = 0.0

    @property
    def overall(self) -> float:
        weights = {"analysis": 0.15, "modeling": 0.25, "coding": 0.35, "paper": 0.25}
        return sum(
            getattr(self, k) * w for k, w in weights.items()
        )


@dataclass
class Task:
    id: str
    name: str
    description: str = ""
    problem_text: str = ""
    language: str = "python"
    template_id: str = "cumcm"
    status: TaskStatus = TaskStatus.PENDING
    progress: PhaseProgress = field(default_factory=PhaseProgress)
    agent_status: dict[str, str] = field(default_factory=lambda: {
        "coordinator": "idle", "modeler": "idle",
        "coder": "idle", "writer": "idle",
    })
    notes: str = ""
    paper_content: Optional[str] = None
    code: Optional[str] = None
    figures: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ── 消息 ──────────────────────────────────────────────

@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


# ── 事件 ──────────────────────────────────────────────

class EventType(str, Enum):
    PROGRESS = "progress"
    LOG = "log"
    STATUS_CHANGE = "status_change"
    ERROR = "error"


@dataclass
class DomainEvent:
    type: EventType
    task_id: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
