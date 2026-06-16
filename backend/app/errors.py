"""统一异常层次"""

from typing import Any


class AppError(Exception):
    """应用异常基类"""

    def __init__(self, message: str, code: str = "UNKNOWN", detail: Any = None):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(message)


class TaskNotFoundError(AppError):
    def __init__(self, task_id: str):
        super().__init__(f"任务不存在: {task_id}", "TASK_NOT_FOUND", {"task_id": task_id})


class TaskInvalidStateError(AppError):
    def __init__(self, task_id: str, current: str, expected: str):
        super().__init__(
            f"任务状态不允许: 当前={current}, 期望={expected}",
            "TASK_INVALID_STATE",
            {"task_id": task_id, "current": current, "expected": expected},
        )


class AgentExecutionError(AppError):
    def __init__(self, agent: str, reason: str):
        super().__init__(f"Agent 执行失败 [{agent}]: {reason}", "AGENT_ERROR", {"agent": agent})


class LLMError(AppError):
    def __init__(self, message: str, provider: str = "", status_code: int = 0):
        super().__init__(message, "LLM_ERROR", {"provider": provider, "status": status_code})


class ConfigError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "CONFIG_ERROR")
