"""流水线引擎 — 轻量级 Agent 编排器"""

import uuid
import traceback
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable

from loguru import logger

from app.config import get_config, AppConfig
from app.domain import Task, TaskStatus, PhaseProgress, DomainEvent, EventType
from app.domain.agent.coordinator import CoordinatorAgent
from app.domain.agent.modeler import ModelerAgent
from app.domain.agent.coder import CoderAgent
from app.domain.agent.writer import WriterAgent
from app.infrastructure.llm import create_llm
from app.infrastructure.events import get_event_bus
from app.infrastructure.sandbox import CodeSandbox


class PipelineEngine:
    """Agent 编排流水线。

    职责：依次调用 Coordinator → Modeler → Coder → Writer。
    不直接操作 LLM，所有 LLM 调用委托给 Agent。
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()
        self.events = get_event_bus()

    async def run(self, task: Task) -> dict[str, Any]:
        """执行完整的建模流水线"""
        task_id = task.id
        word = task.problem_text or task.description
        notes = getattr(task, 'notes', '') or ''

        # RAG 建模知识检索
        rag_context = ""
        try:
            from app.core.engine.rag import rag_engine
            await rag_engine.initialize()
            rag_docs = await rag_engine.search_for_modeling(word, top_k=3)
            if rag_docs:
                rag_context = "\n".join(
                    f"### {d['title']}\n{d['content'][:500]}" for d in rag_docs
                )
                logger.info(f"Pipeline RAG 检索完成 ({len(rag_docs)} 篇)")
        except Exception as e:
            logger.warning(f"Pipeline RAG 检索失败: {e}")

        await self._set_status(task_id, TaskStatus.RUNNING)

        try:
            # ── Stage 1: 问题分析 ──
            await self._emit_progress(task_id, "analysis", 0, "开始分析问题...")
            coordinator = CoordinatorAgent(create_llm(self.config.agent("coordinator")))
            if notes:
                coordinator.set_notes(notes)
            analysis = await coordinator.execute(problem=word, language=task.language)
            await self._emit_progress(task_id, "analysis", 100, "问题分析完成")
            await self._emit_log(task_id, "coordinator", str(analysis)[:500])

            # ── Stage 2: 数学建模 ──
            await self._emit_progress(task_id, "modeling", 0, "开始建立数学模型...")
            modeler = ModelerAgent(create_llm(self.config.agent("modeler")))
            if notes:
                modeler.set_notes(notes)
            model = await modeler.execute(
                analysis=analysis,
                problem=word,
                rag_context=rag_context,
            )
            await self._emit_progress(task_id, "modeling", 100, "模型建立完成")
            await self._emit_log(task_id, "modeler", str(model)[:500])

            # ── Stage 3: 代码生成 + 执行 ──
            await self._emit_progress(task_id, "coding", 0, "开始生成代码...")
            coder = CoderAgent(create_llm(self.config.agent("coder")))
            if notes:
                coder.set_notes(notes)
            sandbox = CodeSandbox(timeout=120)
            code_result = await coder.execute(
                analysis=analysis,
                model=model,
                language=task.language,
                sandbox=sandbox,
            )
            await self._emit_progress(task_id, "coding", 100, "代码生成完成")
            await self._emit_log(task_id, "coder", code_result.get("code", "")[:500])

            # ── Stage 4: 论文撰写 ──
            await self._emit_progress(task_id, "paper", 0, "开始撰写论文...")
            writer = WriterAgent(create_llm(self.config.agent("writer")))
            if notes:
                writer.set_notes(notes)
            paper = await writer.execute(
                analysis=analysis,
                model=model,
                code_result=code_result.get("execution_result") or {},
                problem=word,
                template=task.template_id,
            )
            await self._emit_progress(task_id, "paper", 100, "论文完成")

            result = {
                "analysis": analysis,
                "model": model,
                "code": code_result.get("code", ""),
                "execution_result": code_result.get("execution_result"),
                "paper_content": paper.get("paper_content", ""),
                "figures": code_result.get("execution_result", {}).get("figures", []),
            }

            await self._set_status(task_id, TaskStatus.COMPLETED)
            await self._emit_log(task_id, "system", "🎉 建模任务完成")
            return result

        except Exception as e:
            logger.error(f"Pipe 执行失败 [{task_id}]: {e}")
            traceback.print_exc()
            await self._set_status(task_id, TaskStatus.FAILED)
            await self._emit_log(task_id, "system", f"❌ 任务失败: {e}", "error")
            raise

    # ── 内部辅助 ───────────────────────────────────────

    async def _set_status(self, task_id: str, status: TaskStatus):
        await self.events.publish(f"task:{task_id}:messages", DomainEvent(
            type=EventType.STATUS_CHANGE,
            task_id=task_id,
            data={"status": status.value},
        ))

    async def _emit_progress(self, task_id: str, phase: str, value: float, msg: str):
        await self.events.emit_progress(task_id, phase, value, msg)

    async def _emit_log(self, task_id: str, agent: str, content: str, level: str = "info"):
        await self.events.emit_log(task_id, agent, content, level)
