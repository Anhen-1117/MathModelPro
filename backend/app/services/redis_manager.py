"""Redis 管理器"""

import json
import asyncio
from typing import Any, Optional, Callable, Dict
from loguru import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed, using in-memory fallback")


class RedisManager:
    """Redis 管理器（带内存降级）"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client = None
        self.memory_store: Dict[str, Any] = {}
        self.pubsub_channels: Dict[str, list] = {}
    
    async def connect(self):
        """连接 Redis"""
        if REDIS_AVAILABLE:
            try:
                self.client = aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    protocol=2,  # RESP2 协议，兼容 Redis 3.0+
                )
                await self.client.ping()
                logger.info("Redis connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using memory")
                self.client = None
        else:
            logger.info("Using in-memory store")
    
    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.close()
    
    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        if self.client:
            return await self.client.get(key)
        return self.memory_store.get(key)
    
    async def set(self, key: str, value: str, expire: int = None):
        """设置值"""
        if self.client:
            await self.client.set(key, value, ex=expire)
        else:
            self.memory_store[key] = value
    
    async def delete(self, key: str):
        """删除值"""
        if self.client:
            await self.client.delete(key)
        else:
            self.memory_store.pop(key, None)
    
    async def publish(self, channel: str, message: dict):
        """发布消息"""
        if self.client:
            await self.client.publish(channel, json.dumps(message, default=str))
        else:
            # 内存模式：直接通知订阅者
            if channel in self.pubsub_channels:
                for callback in self.pubsub_channels[channel]:
                    try:
                        await callback(message)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
    
    def subscribe(self, channel: str, callback: Callable):
        """订阅频道（内存模式）"""
        if channel not in self.pubsub_channels:
            self.pubsub_channels[channel] = []
        self.pubsub_channels[channel].append(callback)
    
    async def publish_message(self, task_id: str, message: dict):
        """发布任务消息"""
        channel = f"task:{task_id}:messages"
        await self.publish(channel, message)
    
    async def publish_progress(self, task_id: str, progress: dict):
        """发布进度更新（带 type 标记，前端 WebSocket 据此更新进度条）"""
        channel = f"task:{task_id}:progress"
        await self.publish(channel, {
            "type": "progress",
            "data": {
                "overall_progress": progress.get("overall", 0),
                "phases": progress,
                "agents": {}  # agent_status 由 log 回调单独更新
            }
        })


# 全局实例
redis_manager = RedisManager()
