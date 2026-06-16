"""API 契约 — Pydantic 请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Optional


# ── 任务 ──────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    problem_text: str = ""
    language: str = "python"
    template_id: str = "cumcm"
    notes: str = Field(default="", max_length=2000)  # 用户特殊要求


class TaskResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    problem_text: str = ""
    language: str = "python"
    template_id: str = "cumcm"
    status: str
    progress: dict
    agent_status: dict = {}
    paper_content: Optional[str] = None
    code: Optional[str] = None
    notes: str = ""
    figures: list = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


# ── Agent 配置 ─────────────────────────────────────────

class AgentConfigModel(BaseModel):
    apiKey: str = ""
    baseUrl: str = "https://api.deepseek.com"
    modelId: str = "deepseek-chat"
    apiType: str = "openai"


class SaveApiConfigRequest(BaseModel):
    coordinator: AgentConfigModel
    modeler: AgentConfigModel
    coder: AgentConfigModel
    writer: AgentConfigModel
    openalex_email: str = ""


class SaveApiConfigResponse(BaseModel):
    success: bool
    message: str


# ── 设置 ──────────────────────────────────────────────

class SettingsResponse(BaseModel):
    api: dict[str, dict]
    model: dict


class UpdateSettingsRequest(BaseModel):
    api: Optional[dict] = None
    model: Optional[dict] = None


# ── 聊天 ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    reply: str


# ── 验证 ──────────────────────────────────────────────

class ValidateApiKeyRequest(BaseModel):
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model_id: str = "deepseek-chat"
    api_type: str = "openai"


class ValidateApiKeyResponse(BaseModel):
    valid: bool
    message: str
