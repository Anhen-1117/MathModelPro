"""事件总线 — 发布/订阅，支持 Redis 和内存两种模式"""

import asyncio
import json
from typing import Any, Callable, Awaitable

from app.domain import DomainEvent, EventType

# 回调类型
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """事件总线。

    支持两种模式：
    - Redis 模式：生产级 Pub/Sub
    - 内存模式：开发/无 Redis 环境
    """

    def __init__(self, redis_url: str = ""):
        self._redis_url = redis_url
        self._redis = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    async def connect(self):
        """连接 Redis（可选）"""
        if not self._redis_url:
            return
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                self._redis_url,
                socket_connect_timeout=2,
            )
        except Exception:
            self._redis = None

    async def disconnect(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def subscribe(self, channel: str, handler: EventHandler):
        """订阅频道"""
        async with self._lock:
            if channel not in self._handlers:
                self._handlers[channel] = []
            self._handlers[channel].append(handler)

    async def publish(self, channel: str, event: DomainEvent):
        """发布事件到频道"""
        data = json.dumps({
            "type": event.type.value,
            "task_id": event.task_id,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
        }, default=str)

        # Redis 模式
        if self._redis:
            try:
                await self._redis.publish(channel, data)
            except Exception:
                pass

        # 内存模式通知
        handlers = self._handlers.get(channel, [])
        if handlers:
            await asyncio.gather(
                *(h(event) for h in handlers),
                return_exceptions=True,
            )

    async def emit_progress(self, task_id: str, phase: str, value: float, message: str = ""):
        """快捷方法：发送进度事件"""
        await self.publish(
            f"task:{task_id}:progress",
            DomainEvent(
                type=EventType.PROGRESS,
                task_id=task_id,
                data={"phase": phase, "value": value, "message": message},
            ),
        )

    async def emit_log(self, task_id: str, agent: str, content: str, level: str = "info"):
        """快捷方法：发送日志事件"""
        await self.publish(
            f"task:{task_id}:messages",
            DomainEvent(
                type=EventType.LOG,
                task_id=task_id,
                data={"agent": agent, "content": content, "level": level},
            ),
        )


# ── 全局实例 ──────────────────────────────────────────

_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
