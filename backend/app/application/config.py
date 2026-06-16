"""ConfigService — 配置读写"""

from typing import Any

from app.config import get_config, AppConfig, AgentConfig, ConfigLoader, reload_config


class ConfigService:

    def get(self) -> AppConfig:
        return get_config()

    def get_agent(self, name: str) -> AgentConfig:
        return get_config().agent(name)

    def save(self, configs: dict[str, dict[str, str]], openalex_email: str = ""):
        """从前端格式保存 API 配置"""
        old = get_config()
        cfg = AppConfig(
            coordinator=self._to_agent(configs.get("coordinator", {})),
            modeler=self._to_agent(configs.get("modeler", {})),
            coder=self._to_agent(configs.get("coder", {})),
            writer=self._to_agent(configs.get("writer", {})),
            default_language=old.default_language,
            default_template=old.default_template,
            openalex_email=openalex_email,
        )
        ConfigLoader.save(cfg)
        reload_config()
        return cfg

    def save_model(self, model: dict):
        """仅保存 model 设置（保留已有 API 配置）"""
        old = get_config()
        cfg = AppConfig(
            coordinator=old.coordinator,
            modeler=old.modeler,
            coder=old.coder,
            writer=old.writer,
            default_language=model.get("defaultLanguage", old.default_language),
            default_template=model.get("defaultTemplate", old.default_template),
            openalex_email=old.openalex_email,
        )
        ConfigLoader.save(cfg)
        reload_config()

    def get_safe(self) -> dict[str, Any]:
        """获取脱敏后的配置（返回给前端）"""
        cfg = get_config()
        api = {}
        for name, agent in cfg.all_agents().items():
            key = agent.api_key
            if not key:
                masked = ""
            elif len(key) <= 8:
                masked = "****"
            else:
                masked = key[:4] + "****" + key[-4:]
            api[name] = {
                "apiKey": masked,
                "baseUrl": agent.base_url,
                "modelId": agent.model_id,
                "apiType": agent.api_type,
            }
        return {
            "api": api,
            "model": {
                "defaultLanguage": cfg.default_language,
                "defaultTemplate": cfg.default_template,
            },
        }

    async def validate_key(self, api_key: str, base_url: str,
                           model_id: str, api_type: str = "openai") -> tuple[bool, str]:
        """验证 API Key"""
        from app.infrastructure.llm import create_llm

        cfg = AgentConfig(
            api_key=api_key, base_url=base_url,
            model_id=model_id, api_type=api_type,
        )
        try:
            llm = create_llm(cfg)
            await llm.chat([{"role": "user", "content": "hi"}], max_tokens=1)
            return True, "✓ API Key 验证成功"
        except Exception as e:
            err = str(e)
            if "401" in err:
                return False, "✗ API Key 无效"
            if "403" in err:
                return False, "✗ 权限不足或余额不足"
            return False, f"✗ 验证失败: {err[:100]}"

    @staticmethod
    def _to_agent(data: dict) -> AgentConfig:
        return AgentConfig(
            api_key=data.get("apiKey", ""),
            base_url=data.get("baseUrl", "https://api.deepseek.com"),
            model_id=data.get("modelId", "deepseek-chat"),
            api_type=data.get("apiType", "openai"),
        )
