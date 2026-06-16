"""进度 API"""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
from app.services.redis_manager import redis_manager

router = APIRouter()

# WebSocket 连接管理
connections: Dict[str, List[WebSocket]] = {}
_conn_lock = asyncio.Lock()


async def _safe_send_and_prune(task_id: str, message: str):
    """发送消息给所有连接，并清理已断开的连接"""
    if task_id not in connections:
        return
    dead: List[WebSocket] = []
    for ws in connections[task_id]:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    # 清理死连接
    if dead:
        async with _conn_lock:
            if task_id in connections:
                connections[task_id] = [ws for ws in connections[task_id] if ws not in dead]
                if not connections[task_id]:
                    del connections[task_id]


@router.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """WebSocket 进度推送"""
    await websocket.accept()

    async with _conn_lock:
        if task_id not in connections:
            connections[task_id] = []
        connections[task_id].append(websocket)

    # 订阅 Redis 频道
    async def message_handler(message):
        if task_id in connections:
            await _safe_send_and_prune(task_id, json.dumps(message, default=str))

    redis_manager.subscribe(f"task:{task_id}:messages", message_handler)
    redis_manager.subscribe(f"task:{task_id}:progress", message_handler)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        # 确保断开时清理
        async with _conn_lock:
            if task_id in connections:
                try:
                    connections[task_id].remove(websocket)
                except ValueError:
                    pass  # 可能已被 _safe_send_and_prune 清理
                if not connections[task_id]:
                    del connections[task_id]


async def broadcast_message(task_id: str, message: dict):
    """广播消息（自动清理死连接）"""
    if task_id in connections:
        await _safe_send_and_prune(task_id, json.dumps(message, default=str))


@router.get("/progress/{task_id}")
async def get_progress(task_id: str):
    """获取任务进度（从 SQLite 读取真实进度）"""
    from app.models.database import TaskDB, SessionLocal
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            return {"task_id": task_id, "phase": "idle", "overall_progress": 0}

        prog = task.progress or {}
        return {
            "task_id": task_id,
            "phase": task.status or "idle",
            "overall_progress": prog.get("overall", 0),
            "phases": {
                "analysis": prog.get("analysis", 0),
                "modeling": prog.get("modeling", 0),
                "coding": prog.get("coding", 0),
                "paper": prog.get("paper", 0),
            }
        }
    finally:
        db.close()


@router.get("/progress/{task_id}/logs")
async def get_progress_logs(task_id: str, limit: int = 100):
    """获取进度日志"""
    return {"task_id": task_id, "logs": []}
