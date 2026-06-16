"""A2A Handoff + Fallback 容错系统

四层容错机制：
1. 有限重试 (Retry) — 指数退避重试
2. Fallback Hand Off — 主模型故障自动切换备用模型
3. Evaluator Shadow Mode — 并行评估不阻塞主线
4. Feedback Rerun — 评估不通过自动反馈重跑
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class FallbackStrategy(str, Enum):
    SEQUENTIAL = "sequential"     # 按顺序尝试
    PARALLEL = "parallel"          # 并行尝试，取最快成功的
    ROUND_ROBIN = "round_robin"    # 轮询


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    api_key: str
    base_url: str = ""
    model_id: str = ""
    api_type: str = "openai"
    priority: int = 0  # 优先级（越小越优先）
    max_retries: int = 3


@dataclass
class HandoffEvent:
    """切换事件"""
    timestamp: str
    from_model: str
    to_model: str
    reason: str
    success: bool


class HandoffManager:
    """Handoff 管理器

    管理多模型之间的自动切换，实现高可用性。
    """

    def __init__(self):
        self.models: Dict[str, ModelConfig] = {}
        self.history: List[HandoffEvent] = []
        self.strategy = FallbackStrategy.SEQUENTIAL

    def register_model(self, config: ModelConfig):
        """注册模型"""
        self.models[config.name] = config
        logger.info(f"注册模型: {config.name} (优先级: {config.priority})")

    def remove_model(self, name: str):
        """移除模型"""
        self.models.pop(name, None)

    def _get_ordered_models(self) -> List[ModelConfig]:
        """按优先级排序的模型列表"""
        return sorted(self.models.values(), key=lambda m: m.priority)

    async def execute_with_fallback(
        self,
        primary_model: str,
        task_fn: Callable,
        *args,
        fallback_models: List[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """执行任务，失败时自动切换到备用模型

        Args:
            primary_model: 主模型名称
            task_fn: 异步任务函数，签名为 async def fn(llm_config, *args, **kwargs) -> Dict
            fallback_models: 备选模型列表（按优先级排序）
            *args, **kwargs: 传递给 task_fn 的参数

        Returns:
            任务结果，包含 _handoff_info 字段
        """
        if fallback_models is None:
            # 使用所有注册模型中优先级低于主模型的
            ordered = self._get_ordered_models()
            primary_idx = next((i for i, m in enumerate(ordered) if m.name == primary_model), -1)
            fallback_models = [m.name for m in ordered[primary_idx + 1:]]

        # 构建尝试顺序
        attempt_models = [primary_model] + fallback_models
        last_error = None

        for model_name in attempt_models:
            model = self.models.get(model_name)
            if not model:
                logger.warning(f"模型 {model_name} 未注册，跳过")
                continue

            llm_config = {
                "api_key": model.api_key,
                "base_url": model.base_url,
                "model": model.model_id,
                "api_type": model.api_type,
            }

            for retry in range(model.max_retries):
                try:
                    result = await task_fn(llm_config, *args, **kwargs)

                    # 记录成功的 Handoff
                    if model_name != primary_model:
                        event = HandoffEvent(
                            timestamp=str(asyncio.get_event_loop().time()),
                            from_model=primary_model,
                            to_model=model_name,
                            reason=f"主模型失败: {str(last_error)[:100]}",
                            success=True,
                        )
                        self.history.append(event)

                    result["_handoff_info"] = {
                        "model_used": model_name,
                        "is_fallback": model_name != primary_model,
                        "retry_count": retry,
                    }
                    return result

                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"模型 {model_name} 尝试 {retry + 1}/{model.max_retries} 失败: {str(e)[:200]}"
                    )
                    if retry < model.max_retries - 1:
                        await asyncio.sleep(2 ** retry)  # 指数退避

            # 记录失败的 Handoff
            event = HandoffEvent(
                timestamp=str(asyncio.get_event_loop().time()),
                from_model=primary_model,
                to_model=model_name,
                reason=str(last_error)[:200] if last_error else "未知错误",
                success=False,
            )
            self.history.append(event)

        raise RuntimeError(
            f"所有模型尝试失败 ({', '.join(attempt_models)})。最后错误: {str(last_error)[:200] if last_error else '未知'}"
        )

    def get_history(self) -> List[Dict[str, Any]]:
        """获取切换历史"""
        return [
            {
                "timestamp": e.timestamp,
                "from": e.from_model,
                "to": e.to_model,
                "reason": e.reason,
                "success": e.success,
            }
            for e in self.history
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.history)
        successes = sum(1 for e in self.history if e.success)
        return {
            "total_handoffs": total,
            "successful_handoffs": successes,
            "failure_rate": f"{(total - successes) / max(1, total) * 100:.1f}%",
            "models_registered": len(self.models),
            "strategy": self.strategy.value,
        }


class RetryHandler:
    """增强重试处理器

    支持：
    - 指数退避 (Exponential Backoff)
    - 抖动 (Jitter) 避免惊群效应
    - 条件重试（只重试特定错误）
    - 最大延迟限制
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """计算第 attempt 次重试的延迟"""
        import random
        delay = self.base_delay * (self.exponential_base ** attempt)
        if self.jitter:
            delay *= 0.5 + random.random()
        return min(delay, self.max_delay)

    async def execute(
        self,
        fn: Callable,
        *args,
        should_retry: Callable[[Exception], bool] = None,
        on_retry: Callable[[Exception, int], None] = None,
        **kwargs,
    ):
        """执行函数，自动重试

        Args:
            fn: 要执行的异步函数
            should_retry: 判断是否应该重试的回调
            on_retry: 重试时的回调
        """
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    if should_retry and not should_retry(e):
                        raise
                    delay = self.get_delay(attempt)
                    logger.warning(f"重试 {attempt + 1}/{self.max_retries}，等待 {delay:.1f}s: {str(e)[:100]}")
                    if on_retry:
                        on_retry(e, attempt + 1)
                    await asyncio.sleep(delay)
        raise last_error


# 全局实例
handoff_manager = HandoffManager()
retry_handler = RetryHandler()

# 注册默认模型（从环境变量读取备用模型配置）
import os
_default_primary = os.getenv("PRIMARY_MODEL", "deepseek")
_default_fallback = os.getenv("FALLBACK_MODEL", "")

# 主模型始终注册
handoff_manager.register_model(ModelConfig(
    name="deepseek",
    api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com",
    model_id="deepseek-chat",
    api_type="openai",
    priority=0,
))

# 如果配置了 OpenAI 备用
if os.getenv("OPENAI_API_KEY"):
    handoff_manager.register_model(ModelConfig(
        name="openai",
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url="https://api.openai.com",
        model_id="gpt-4o",
        api_type="openai",
        priority=1,
    ))

# 如果配置了 Anthropic 备用
if os.getenv("ANTHROPIC_API_KEY"):
    handoff_manager.register_model(ModelConfig(
        name="anthropic",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url="https://api.anthropic.com",
        model_id="claude-sonnet-4-20250514",
        api_type="anthropic",
        priority=2,
    ))
