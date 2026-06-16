"""对话 API — 支持流式和非流式"""

import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncIterator
from app.core.llm.litellm_provider import LLMFactory
from app.utils.llm_config import load_llm_config

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    task_id: Optional[str] = None
    model: str = "deepseek-chat"


class ChatResponse(BaseModel):
    reply: str
    model: str
    tokens_used: int = 0


def get_llm():
    """获取 LLM 实例（使用统一配置工具）"""
    llm_cfg = load_llm_config("coordinator")
    if llm_cfg.is_configured:
        return LLMFactory.create(
            api_key=llm_cfg.api_key,
            base_url=llm_cfg.base_url,
            model=llm_cfg.model
        )
    return None


@router.post("/chat")
async def chat(request: ChatRequest):
    """对话接口"""
    llm = get_llm()
    
    if llm:
        try:
            messages = [
                {"role": "system", "content": "你是 MathModelPro 数学建模助手，用中文回复。"},
                {"role": "user", "content": request.message}
            ]
            response = await llm.chat(messages)
            return ChatResponse(
                reply=response["content"],
                model=request.model,
                tokens_used=response.get("usage", {}).get("total_tokens", 0)
            )
        except Exception as e:
            return ChatResponse(
                reply=f"LLM 调用失败: {str(e)}\n\n请检查 API Key 配置。",
                model=request.model
            )
    
    return ChatResponse(
        reply=f"收到你的消息：{request.message}\n\n请先在设置页面配置 API Key。",
        model=request.model
    )


@router.post("/chat/analyze")
async def analyze_problem(request: ChatRequest):
    """分析问题接口"""
    llm = get_llm()
    
    if llm:
        try:
            messages = [
                {"role": "system", "content": "你是数学建模协调器，负责分析问题。用 JSON 格式回复。"},
                {"role": "user", "content": f"请分析以下数学建模问题：\n\n{request.message}"}
            ]
            response = await llm.chat(messages)
            return {"analysis": {"content": response["content"]}, "suggestion": "已分析"}
        except Exception as e:
            return {"error": str(e)}
    
    return {
        "analysis": {
            "problem_type": "优化问题",
            "key_variables": ["x", "y"],
            "constraints": [],
            "objective": "目标函数"
        },
        "suggestion": "请先配置 API Key"
    }


# ── 流式端点 ────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口 — SSE (Server-Sent Events)"""
    llm = get_llm()

    async def generate() -> AsyncIterator[str]:
        if llm:
            try:
                messages = [
                    {"role": "system", "content": "你是 MathModelPro 数学建模助手，用中文回复。"},
                    {"role": "user", "content": request.message},
                ]
                async for token in llm.chat_stream(messages):
                    yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        else:
            yield f"data: {json.dumps({'token': '请先在设置页面配置 API Key。'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
