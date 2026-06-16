"""系统设置 API"""

import json
import os
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from loguru import logger
from app._config_loader import load_raw_config, save_raw_config

router = APIRouter()

# 默认配置
DEFAULT_CONFIG = {
    "api": {
        "coordinator": {"apiKey": "", "baseUrl": "https://api.deepseek.com", "modelId": "deepseek-chat"},
        "modeler": {"apiKey": "", "baseUrl": "https://api.deepseek.com", "modelId": "deepseek-chat"},
        "coder": {"apiKey": "", "baseUrl": "https://api.deepseek.com", "modelId": "deepseek-chat"},
        "writer": {"apiKey": "", "baseUrl": "https://api.deepseek.com", "modelId": "deepseek-chat"}
    },
    "model": {
        "defaultLanguage": "python",
        "defaultTemplate": "cumcm"
    }
}


def load_config():
    """加载配置（委托统一加载器）"""
    cfg = load_raw_config()
    return cfg if cfg else DEFAULT_CONFIG.copy()


def save_config(data: Dict[str, Any] = None):
    """保存配置到磁盘"""
    if data is not None:
        save_raw_config(data)
    else:
        save_raw_config(load_config())


class UpdateSettingsRequest(BaseModel):
    api: Optional[Dict[str, Any]] = None
    model: Optional[Dict[str, Any]] = None


def _mask_api_key(key: str) -> str:
    """脱敏 API Key：保留前 4 后 4 字符"""
    if not key or len(key) <= 8:
        return key
    return key[:4] + "****" + key[-4:]


@router.get("/settings")
async def get_settings():
    """获取系统设置（API Key 已脱敏）"""
    cfg = load_config()
    # 返回脱敏后的配置
    safe_config = json.loads(json.dumps(cfg))  # 深拷贝
    api_section = safe_config.get("api", {})
    for agent_name in api_section:
        if "apiKey" in api_section[agent_name]:
            api_section[agent_name]["apiKey"] = _mask_api_key(api_section[agent_name]["apiKey"])
    return safe_config


@router.put("/settings")
async def update_settings(request: UpdateSettingsRequest):
    """更新系统设置"""
    cfg = load_config()

    if request.api is not None:
        for agent_name, agent_cfg in request.api.items():
            key_len = len(agent_cfg.get("apiKey", "")) if isinstance(agent_cfg, dict) else 0
            logger.info(f"更新 Agent [{agent_name}]: Key长度={key_len}, 模型={agent_cfg.get('modelId', '?') if isinstance(agent_cfg, dict) else '?'}")
        cfg["api"] = request.api
    if request.model is not None:
        cfg["model"] = request.model

    save_config(cfg)
    logger.info(f"设置已更新并持久化")
    return {"message": "Settings updated", "config": cfg}


@router.get("/settings/api-key")
async def get_api_key(agent_type: str = "coordinator"):
    """获取指定 Agent 的 API Key"""
    cfg = load_config()

    agent_config = cfg.get("api", {}).get(agent_type, {})
    api_key = agent_config.get("apiKey", "")

    # 脱敏显示
    if api_key and len(api_key) > 8:
        masked = api_key[:4] + "****" + api_key[-4:]
    else:
        masked = "未配置"

    return {
        "agent_type": agent_type,
        "has_key": bool(api_key),
        "masked_key": masked
    }


# ── OpenAlex Email 验证 ─────────────────────────────────────

class ValidateOpenalexEmailRequest(BaseModel):
    """验证 OpenAlex Email 的请求体"""
    email: str


class ValidateOpenalexEmailResponse(BaseModel):
    """验证 OpenAlex Email 的响应体"""
    valid: bool
    message: str


@router.post("/validate-openalex-email", response_model=ValidateOpenalexEmailResponse)
async def validate_openalex_email(request: ValidateOpenalexEmailRequest):
    """
    验证 OpenAlex Email 的有效性。
    向 OpenAlex API 发送测试请求验证邮箱是否可用。
    """
    import httpx

    # 空邮箱直接拒绝
    if not request.email or not request.email.strip():
        return ValidateOpenalexEmailResponse(valid=False, message="✗ Email 不能为空")

    try:
        params = {"mailto": request.email.strip()}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.openalex.org/works", params=params)
            resp.raise_for_status()
        return ValidateOpenalexEmailResponse(valid=True, message="✓ OpenAlex Email 验证成功")
    except Exception as e:
        error_msg = str(e)[:100]
        logger.warning(f"OpenAlex Email 验证失败: {error_msg}")
        return ValidateOpenalexEmailResponse(
            valid=False, message=f"✗ OpenAlex Email 验证失败: {error_msg}"
        )


# ── 模板样式（供 Word/PDF 共享）──────────────────────────

from app.utils.paper_style import get_template_list, to_css, get_style


@router.get("/template/styles")
async def get_template_styles(template_id: str = "cumcm"):
    """返回模板 CSS 样式（供前端 PDF 打印使用）"""
    css = to_css(template_id)
    style = get_style(template_id)
    return {
        "css": css,
        "template": style["template"],
        "page": style["page"],
        "fonts": style["fonts"],
        "sizes": style["sizes"],
        "paragraph": style["paragraph"],
        "table": style["table"],
        "code": style["code"],
    }


@router.get("/templates")
async def list_templates():
    """返回可用模板列表"""
    return {"templates": get_template_list()}
