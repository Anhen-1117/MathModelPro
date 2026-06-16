"""V1 兼容桥接 — 重新导出到 infrastructure/llm.py"""

from app.infrastructure.llm import LLMAdapter as LLMProvider, create_llm
from app.config import AgentConfig


class LLMFactory:
    @staticmethod
    def create(api_key="", base_url=None, model="deepseek-chat", api_type="openai"):
        return LLMProvider(AgentConfig(
            api_key=api_key, base_url=base_url or "https://api.deepseek.com",
            model_id=model, api_type=api_type,
        ))

    @staticmethod
    def create_from_config(config: dict):
        return LLMProvider(AgentConfig(
            api_key=config.get("apiKey", ""),
            base_url=config.get("baseUrl", "https://api.deepseek.com"),
            model_id=config.get("modelId", "deepseek-chat"),
            api_type=config.get("apiType", "openai"),
        ))
