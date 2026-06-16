"""统一的 LLM 配置解析工具

解决项目中 apiKey/api_key、modelId/model 等 key 命名不一致的问题。
"""

from typing import Dict, Any, Optional
import os


class LLMConfig:
    """标准化的 LLM 配置"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        api_type: str = "openai",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.api_type = api_type
        self.temperature = temperature
        self.max_tokens = max_tokens

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "api_type": self.api_type,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def to_legacy_llm_config(self) -> Dict[str, Any]:
        """转换为 WorkflowEngine 需要的 llm config 格式"""
        return {
            "llm": {
                "api_key": self.api_key,
                "base_url": self.base_url,
                "model": self.model,
                "api_type": self.api_type,
            }
        }

    @classmethod
    def from_settings_config(cls, agent_config: Dict[str, Any]) -> "LLMConfig":
        """从 settings.json 的 agent 配置中解析（兼容多种 key 格式）"""
        api_key = (
            agent_config.get("apiKey")
            or agent_config.get("api_key")
            or os.getenv("LLM_API_KEY", "")
        )
        base_url = (
            agent_config.get("baseUrl")
            or agent_config.get("base_url")
            or "https://api.deepseek.com"
        )
        model = (
            agent_config.get("modelId")
            or agent_config.get("model_id")
            or agent_config.get("model")
            or "deepseek-chat"
        )
        api_type = (
            agent_config.get("apiType")
            or agent_config.get("api_type")
            or "openai"
        )
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            api_type=api_type,
        )

    @classmethod
    def from_project_config(cls, config: Dict[str, Any], agent_name: str = "coordinator") -> "LLMConfig":
        """从项目 config.json 中读取指定 agent 的配置

        智能回退策略：
        1. 先读 agent 自身配置
        2. 如果自身没配置 API Key，继承 coordinator 的 Key + BaseURL
        3. 如果自身配置了 modelId 则保留，否则也继承 coordinator 的
        """
        api_config = config.get("api", {})
        agent_config = api_config.get(agent_name, {})

        # 读取 coordinator 配置作为回退源
        coordinator_config = api_config.get("coordinator", {})

        # 检查当前 agent 是否已配置（有自己的 API Key）
        agent_api_key = agent_config.get("apiKey") or agent_config.get("api_key") or ""
        coordinator_api_key = coordinator_config.get("apiKey") or coordinator_config.get("api_key") or ""

        # 如果当前 agent 没有 API Key 但 coordinator 有，继承 coordinator 的配置
        if not agent_api_key.strip() and coordinator_api_key.strip():
            merged = {}
            # 基础连接信息从 coordinator 继承
            merged["apiKey"] = coordinator_api_key
            merged["baseUrl"] = (
                coordinator_config.get("baseUrl")
                or coordinator_config.get("base_url")
                or "https://api.deepseek.com"
            )
            merged["apiType"] = (
                coordinator_config.get("apiType")
                or coordinator_config.get("api_type")
                or "openai"
            )
            # 模型 ID：优先用自身配置，其次 coordinator
            merged["modelId"] = (
                agent_config.get("modelId")
                or agent_config.get("model_id")
                or agent_config.get("model")
                or coordinator_config.get("modelId")
                or coordinator_config.get("model_id")
                or coordinator_config.get("model")
                or "deepseek-chat"
            )
            return cls.from_settings_config(merged)

        # 如果 agent 自身有 key 或者 coordinator 也没有 key
        if not agent_config:
            # 回退：使用第一个可用的 agent 配置
            for key in ["coordinator", "modeler", "coder", "writer"]:
                if key in api_config:
                    agent_config = api_config[key]
                    break
        return cls.from_settings_config(agent_config)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def __repr__(self) -> str:
        return f"LLMConfig(model={self.model}, api_type={self.api_type}, has_key={self.is_configured})"


def load_llm_config(agent_name: str = "coordinator") -> LLMConfig:
    """便捷函数：从项目配置加载 LLM 配置（委托统一加载器）

    Args:
        agent_name: agent 名称（coordinator/modeler/coder/writer）

    Returns:
        标准化的 LLMConfig 实例
    """
    from app._config_loader import load_raw_config

    try:
        config = load_raw_config()
        if config:
            return LLMConfig.from_project_config(config, agent_name)
    except Exception:
        pass

    # 回退到环境变量
    return LLMConfig(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
    )
