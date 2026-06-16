"""HIL 人机协作系统 — 关键节点暂停等待用户审批"""

import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class DecisionAction(str, Enum):
    """决策动作"""
    CONFIRM = "confirm"        # 确认继续
    EDIT = "edit"              # 编辑后继续
    REGENERATE = "regenerate"  # 重新生成
    ASK = "ask"                # 追问
    SKIP = "skip"              # 跳过此阶段
    ABORT = "abort"            # 中止流程


@dataclass
class HILCheckpoint:
    """HIL 检查点"""
    id: str
    phase: str           # analysis / modeling / coding / paper
    agent: str           # coordinator / modeler / coder / writer
    question: str        # 向用户展示的问题
    preview: str         # 预览内容（Agent 的输出）
    options: List[str]   # 可选动作
    status: str = "waiting"  # waiting / resolved / timeout
    user_action: Optional[str] = None
    user_input: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class HILManager:
    """HIL 管理器"""

    def __init__(self):
        self._pending: Dict[str, HILCheckpoint] = {}
        self._resolved: Dict[str, HILCheckpoint] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._wait_events: Dict[str, asyncio.Event] = {}

    def create_checkpoint(
        self,
        phase: str,
        agent: str,
        question: str,
        preview: str,
        options: List[str] = None,
        timeout: int = 300,
    ) -> str:
        """创建检查点，返回 checkpoint ID"""
        cp_id = str(uuid.uuid4())[:8]
        checkpoint = HILCheckpoint(
            id=cp_id,
            phase=phase,
            agent=agent,
            question=question,
            preview=preview,
            options=options or [
                DecisionAction.CONFIRM.value,
                DecisionAction.REGENERATE.value,
                DecisionAction.EDIT.value,
                DecisionAction.SKIP.value,
            ],
        )
        self._pending[cp_id] = checkpoint
        self._wait_events[cp_id] = asyncio.Event()
        logger.info(f"HIL checkpoint created: {cp_id} [{phase}/{agent}]")
        return cp_id

    async def wait_for_decision(self, cp_id: str, timeout: int = 300) -> HILCheckpoint:
        """等待用户决策"""
        event = self._wait_events.get(cp_id)
        if not event:
            raise ValueError(f"Checkpoint {cp_id} not found")

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending[cp_id].status = "timeout"
            self._pending[cp_id].user_action = DecisionAction.CONFIRM.value
            logger.warning(f"HIL checkpoint {cp_id} timed out, auto-confirming")

        checkpoint = self._pending.pop(cp_id, None)
        if checkpoint:
            self._resolved[cp_id] = checkpoint
        return checkpoint

    def resolve(self, cp_id: str, action: str, user_input: str = None) -> bool:
        """用户做出决策"""
        checkpoint = self._pending.get(cp_id)
        if not checkpoint:
            return False

        checkpoint.status = "resolved"
        checkpoint.user_action = action
        checkpoint.user_input = user_input

        event = self._wait_events.get(cp_id)
        if event:
            event.set()

        logger.info(f"HIL checkpoint {cp_id} resolved: {action}")
        return True

    def get_pending(self) -> List[Dict[str, Any]]:
        """获取所有待决策的检查点"""
        return [
            {
                "id": cp.id,
                "phase": cp.phase,
                "agent": cp.agent,
                "question": cp.question,
                "preview": cp.preview[:500],
                "options": cp.options,
                "status": cp.status,
            }
            for cp in self._pending.values()
        ]

    def get_resolved(self) -> List[Dict[str, Any]]:
        """获取已决策的检查点"""
        return [
            {
                "id": cp.id,
                "phase": cp.phase,
                "agent": cp.agent,
                "action": cp.user_action,
                "input": cp.user_input,
            }
            for cp in self._resolved.values()
        ]

    @property
    def has_pending(self) -> bool:
        return len(self._pending) > 0


# 全局实例
hil_manager = HILManager()
