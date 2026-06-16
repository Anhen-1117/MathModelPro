"""统一 LLM 适配器 — 基于 litellm，实例级线程安全"""

from typing import AsyncIterator
from dataclasses import dataclass, field
from loguru import logger

from app.config import AgentConfig


# ── 类型 ──────────────────────────────────────────────

@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)

    def __getitem__(self, key: str):
        """兼容旧代码字典式访问 resp['content']"""
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


# ── 适配器 ────────────────────────────────────────────

class LLMAdapter:
    """LLM 统一适配器。

    特点：
    - 每次请求独立传递 api_key/api_base，不修改 litellm 全局状态
    - 支持流式和非流式
    - litellm 延迟导入（首次 import 较慢）
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.model = config.to_litellm_model()

    @staticmethod
    def _get_litellm():
        import litellm
        return litellm

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """非流式聊天补全"""
        litellm = self._get_litellm()
        try:
            resp = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=self.config.api_key,
                api_base=self.config.base_url,
                **kwargs,
            )
            choice = resp.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=getattr(resp, "model", ""),
                usage={
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                    "total_tokens": resp.usage.total_tokens if resp.usage else 0,
                },
            )
        except Exception as e:
            logger.error(f"LLM 调用失败 [{self.model}]: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式聊天补全"""
        litellm = self._get_litellm()
        try:
            resp = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                api_key=self.config.api_key,
                api_base=self.config.base_url,
                **kwargs,
            )
            async for chunk in resp:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"LLM 流式调用失败 [{self.model}]: {e}")
            raise


# ── 工厂 ──────────────────────────────────────────────

def create_llm(config: AgentConfig) -> LLMAdapter:
    """从 AgentConfig 创建 LLM 适配器"""
    return LLMAdapter(config)
