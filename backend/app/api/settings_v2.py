"""设置 API（V2）— 薄路由，委托给 ConfigService"""

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_config_service
from app.application.config import ConfigService
from app.schemas import (
    SaveApiConfigRequest, SaveApiConfigResponse,
    ValidateApiKeyRequest, ValidateApiKeyResponse,
    SettingsResponse, UpdateSettingsRequest,
)

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    svc: ConfigService = Depends(get_config_service),
):
    """获取系统设置（API Key 脱敏）"""
    return svc.get_safe()


@router.put("/settings")
async def update_settings(
    request: UpdateSettingsRequest,
    svc: ConfigService = Depends(get_config_service),
):
    """更新系统设置"""
    if request.api is not None:
        svc.save(request.api)
    if request.model is not None:
        svc.save_model(request.model)
    # 返回脱敏后的配置，前端据此显示已配置数量
    return svc.get_safe()


@router.post("/save-api-config", response_model=SaveApiConfigResponse)
async def save_api_config(
    request: SaveApiConfigRequest,
    svc: ConfigService = Depends(get_config_service),
):
    """保存 API 配置"""
    configs = {
        "coordinator": request.coordinator.model_dump(),
        "modeler": request.modeler.model_dump(),
        "coder": request.coder.model_dump(),
        "writer": request.writer.model_dump(),
    }
    svc.save(configs, openalex_email=request.openalex_email)
    configured = sum(
        1 for v in configs.values() if v.get("apiKey", "").strip()
    )
    return SaveApiConfigResponse(
        success=True,
        message=f"配置保存成功 ({configured}/4 个 Agent 已配置)",
    )


@router.post("/validate-api-key", response_model=ValidateApiKeyResponse)
async def validate_api_key(
    request: ValidateApiKeyRequest,
    svc: ConfigService = Depends(get_config_service),
):
    """验证 API Key 有效性"""
    valid, msg = await svc.validate_key(
        request.api_key, request.base_url,
        request.model_id, request.api_type,
    )
    return ValidateApiKeyResponse(valid=valid, message=msg)
