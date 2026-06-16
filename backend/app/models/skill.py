"""Skill 数据模型"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel


class Skill(BaseModel):
    """Skill 定义"""
    id: str
    name: str
    description: str
    agent_type: str  # coordinator/modeler/coder/writer/all
    system_prompt: str
    tools: List[str] = []  # 可用工具列表
    config: Dict[str, Any] = {}  # 额外配置
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    is_builtin: bool = False  # 是否内置


class SkillCreateRequest(BaseModel):
    """创建 Skill 请求"""
    name: str
    description: str
    agent_type: str
    system_prompt: str
    tools: List[str] = []
    config: Dict[str, Any] = {}


class SkillUpdateRequest(BaseModel):
    """更新 Skill 请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class AgentSkillConfig(BaseModel):
    """Agent Skill 配置"""
    agent_type: str
    skill_id: str
    overrides: Dict[str, Any] = {}  # 覆盖配置


class SkillRunRequest(BaseModel):
    """独立执行 Skill 请求"""
    skill_id: str
    params: Dict[str, Any] = {}  # 用户输入的参数（数据描述、图表配置等）
    execute: bool = False  # 是否执行生成的代码
    language: str = "python"  # 代码语言


class SkillRunResponse(BaseModel):
    """独立执行 Skill 响应"""
    skill_id: str
    skill_name: str
    code: str = ""  # 生成的代码
    language: str = "python"
    execution_result: Optional[Dict[str, Any]] = None  # 执行结果（如 execute=True）
    mermaid: str = ""  # Mermaid 图表代码（流程图 Skill）


class ChartPipelineRequest(BaseModel):
    """图表管线请求 — 串联多个 Skill"""
    pipeline: List[Dict[str, Any]]  # [{"skill_id": "...", "params": {...}}, ...]
    execute: bool = True  # 是否执行代码
    parallel: bool = False  # 是否并行执行
    language: str = "python"
