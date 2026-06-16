"""全局配置管理 — 单一入口，统一多个配置来源"""

import json
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


# ── 路径 ──────────────────────────────────────────────

def _project_root() -> Path:
    """项目根目录 = backend/ 的父目录"""
    return Path(__file__).parent.parent


def _data_dir() -> Path:
    return _project_root() / "data"


# ── 模型 ──────────────────────────────────────────────

@dataclass
class AgentConfig:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model_id: str = "deepseek-chat"
    api_type: str = "openai"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("sk-****"))

    def to_litellm_model(self) -> str:
        """转换为 litellm 格式的 model 名称"""
        if self.base_url and "deepseek" in self.base_url and not self.model_id.startswith("deepseek/"):
            return f"deepseek/{self.model_id}"
        return self.model_id


@dataclass
class AppConfig:
    coordinator: AgentConfig = field(default_factory=AgentConfig)
    modeler: AgentConfig = field(default_factory=AgentConfig)
    coder: AgentConfig = field(default_factory=AgentConfig)
    writer: AgentConfig = field(default_factory=AgentConfig)
    default_language: str = "python"
    default_template: str = "cumcm"
    openalex_email: str = ""

    def agent(self, name: str) -> AgentConfig:
        mapping = {
            "coordinator": self.coordinator,
            "modeler": self.modeler,
            "coder": self.coder,
            "writer": self.writer,
        }
        return mapping.get(name, AgentConfig())

    def all_agents(self) -> dict[str, AgentConfig]:
        return {
            "coordinator": self.coordinator,
            "modeler": self.modeler,
            "coder": self.coder,
            "writer": self.writer,
        }


# ── 加载 ──────────────────────────────────────────────

class ConfigLoader:
    """从 config.json 加载配置，支持智能回退（委托统一加载器）"""

    @classmethod
    def load(cls) -> AppConfig:
        from app._config_loader import load_raw_config

        try:
            data = load_raw_config()
        except Exception:
            return AppConfig()

        if not data:
            return AppConfig()

        api = data.get("api", {})
        model = data.get("model", {})

        def _agent(name: str) -> AgentConfig:
            cfg = api.get(name, {})
            return AgentConfig(
                api_key=cls._resolve_key(cfg.get("apiKey", ""), api),
                base_url=cfg.get("baseUrl", "https://api.deepseek.com"),
                model_id=cfg.get("modelId", "deepseek-chat"),
                api_type=cfg.get("apiType", "openai"),
            )

        return AppConfig(
            coordinator=_agent("coordinator"),
            modeler=_agent("modeler"),
            coder=_agent("coder"),
            writer=_agent("writer"),
            default_language=model.get("defaultLanguage", "python"),
            default_template=model.get("defaultTemplate", "cumcm"),
            openalex_email=api.get("openalexEmail", ""),
        )

    @staticmethod
    def _resolve_key(agent_key: str, api: dict) -> str:
        """智能回退：Agent 无独立 Key 时继承 coordinator 的"""
        if agent_key:
            return agent_key
        coordinator_key = api.get("coordinator", {}).get("apiKey", "")
        return coordinator_key

    @classmethod
    def save(cls, config: AppConfig) -> None:
        """保存配置到 config.json（保留 chart_pipeline 等已有字段）"""
        from app._config_loader import load_raw_config, save_raw_config

        # 加载现有配置（保留 chart_pipeline 等字段）
        try:
            data = load_raw_config()
        except Exception:
            data = {}

        # 更新 api 和 model 部分
        data["api"] = {
            name: {
                "apiKey": cfg.api_key,
                "baseUrl": cfg.base_url,
                "modelId": cfg.model_id,
                "apiType": cfg.api_type,
            }
            for name, cfg in config.all_agents().items()
        }
        data["model"] = {
            "defaultLanguage": config.default_language,
            "defaultTemplate": config.default_template,
        }

        save_raw_config(data)


# ── 全局单例 ──────────────────────────────────────────

_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置（懒加载 + 缓存）"""
    global _config
    if _config is None:
        _config = ConfigLoader.load()
    return _config


def reload_config() -> AppConfig:
    """强制重新加载配置"""
    global _config
    _config = ConfigLoader.load()
    return _config
