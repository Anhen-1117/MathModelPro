"""V1 LLM 桥接层 — 重新导出到新架构 infrastructure/llm.py"""

from dataclasses import dataclass, field
from app.infrastructure.llm import LLMAdapter, create_llm, LLMResponse as InfraResponse
from app.config import AgentConfig


# ── V1 兼容类型 ──────────────────────────────────────

@dataclass
class Message:
    role: str
    content: str


LLMResponse = InfraResponse  # 直接复用


class BaseLLM:
    """V1 LLM 基类兼容"""
    def __init__(self, config: AgentConfig):
        self._adapter = LLMAdapter(config)

    async def chat(self, messages: list):
        return await self._adapter.chat([{"role": m.role, "content": m.content} for m in messages] if isinstance(messages[0], Message) else messages)

    async def chat_stream(self, messages: list):
        async for chunk in self._adapter.chat_stream(messages):
            yield chunk

    @staticmethod
    def format_messages(system: str = "", user: str = "", history: list = None):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        if history:
            msgs.extend(history)
        if user:
            msgs.append({"role": "user", "content": user})
        return msgs


# ── V1 工厂兼容 ──────────────────────────────────────

class LLMFactory:
    @staticmethod
    def create(api_key="", base_url=None, model="deepseek-chat", api_type="openai"):
        return LLMAdapter(AgentConfig(
            api_key=api_key, base_url=base_url or "https://api.deepseek.com",
            model_id=model, api_type=api_type,
        ))

    @staticmethod
    def create_from_config(config: dict):
        return LLMAdapter(AgentConfig(
            api_key=config.get("apiKey", ""),
            base_url=config.get("baseUrl", "https://api.deepseek.com"),
            model_id=config.get("modelId", "deepseek-chat"),
            api_type=config.get("apiType", "openai"),
        ))

llm = None

