"""Skill 管理 API — 支持独立执行和管线编排"""

import json
import asyncio
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional, Any
from loguru import logger
from app.models.skill import (
    Skill, SkillCreateRequest, SkillUpdateRequest,
    SkillRunRequest, SkillRunResponse, ChartPipelineRequest
)
from app.services.skill_manager import skill_manager
from app.core.llm import LLMFactory
from app.core.engine.interpreter import LocalInterpreter

router = APIRouter()


@router.get("/skills")
async def list_skills(agent_type: str = None):
    """获取 Skill 列表"""
    if agent_type:
        skills = skill_manager.get_skills_by_agent(agent_type)
    else:
        skills = skill_manager.get_all_skills()
    return {"skills": [s.dict() for s in skills]}


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取单个 Skill"""
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.dict()


@router.post("/skills")
async def create_skill(request: SkillCreateRequest):
    """创建 Skill"""
    skill = skill_manager.create_skill(request)
    return skill.dict()


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, request: SkillUpdateRequest):
    """更新 Skill"""
    skill = skill_manager.update_skill(skill_id, request)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.dict()


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str):
    """删除 Skill"""
    success = skill_manager.delete_skill(skill_id)
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found or builtin")
    return {"message": "Skill deleted"}


# ========== Agent Skill 配置 ==========

@router.get("/agent-skills")
async def get_agent_skills():
    """获取所有 Agent 的 Skill 配置"""
    configs = skill_manager.get_agent_configs()
    result = {}
    for agent_type, skill_id in configs.items():
        skill = skill_manager.get_skill(skill_id)
        result[agent_type] = {
            "skill_id": skill_id,
            "skill_name": skill.name if skill else "Unknown"
        }
    return result


@router.get("/agent-skills/{agent_type}")
async def get_agent_skill(agent_type: str):
    """获取指定 Agent 当前使用的 Skill"""
    skill = skill_manager.get_agent_skill(agent_type)
    if not skill:
        raise HTTPException(status_code=404, detail="No skill configured")
    return {
        "agent_type": agent_type,
        "skill": skill.dict()
    }


@router.post("/agent-skills/{agent_type}")
async def set_agent_skill(agent_type: str, skill_id: str):
    """设置 Agent 使用的 Skill"""
    success = skill_manager.set_agent_skill(agent_type, skill_id)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid skill or agent type")
    return {"message": "Agent skill updated"}


@router.get("/agent-skills/{agent_type}/prompt")
async def get_agent_prompt(agent_type: str):
    """获取 Agent 当前的系统提示词"""
    skill = skill_manager.get_agent_skill(agent_type)
    if not skill:
        raise HTTPException(status_code=404, detail="No skill configured")
    return {
        "agent_type": agent_type,
        "skill_id": skill.id,
        "system_prompt": skill.system_prompt
    }


# ========== 独立执行 Skill ==========

def _build_user_prompt(skill_id: str, params: Dict[str, Any]) -> str:
    """根据 Skill 类型构建用户提示词"""
    # 流程图 Skill 用特殊格式
    if skill_id.startswith("flow-"):
        diagram_type = params.get("diagram_type", "算法流程")
        description = params.get("description", params.get("data", "请描述流程"))
        return f"请生成一个{diagram_type}的 Mermaid 图：\n\n{description}"

    # 数据图表 Skill
    chart_type_map = {
        "chart-line": "折线图",
        "chart-bar": "分组柱状图",
        "chart-scatter": "密度散点图",
        "chart-heatmap": "热力图",
        "chart-box": "箱线图+小提琴图",
        "chart-contour": "等高线图",
        "chart-radar": "雷达图",
        "chart-surface3d": "3D 曲面图",
        "chart-sankey": "桑基图",
        "chart-network": "网络拓扑图",
    }
    chart_type = chart_type_map.get(skill_id, "图表")

    parts = [f"请生成一个学术级的{chart_type}。"]
    if params.get("data"):
        parts.append(f"\n数据描述：{params['data']}")
    if params.get("title"):
        parts.append(f"\n图表标题：{params['title']}")
    if params.get("x_label"):
        parts.append(f"\nX 轴标签：{params['x_label']}")
    if params.get("y_label"):
        parts.append(f"\nY 轴标签：{params['y_label']}")
    for key, val in params.items():
        if key not in ("data", "title", "x_label", "y_label"):
            parts.append(f"\n{key}：{val}")

    return "".join(parts)


async def _execute_code_safe(code: str, language: str) -> Dict[str, Any]:
    """安全执行代码，带超时保护"""
    try:
        interpreter = LocalInterpreter(timeout=120)
        result = await interpreter.execute(code, language)
        return {
            "success": result.success,
            "output": result.output[:2000] if result.output else "",
            "error": result.error[:500] if result.error else "",
            "figures": result.figures or [],
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e)[:500],
            "figures": [],
        }


@router.post("/skills/run", response_model=SkillRunResponse)
async def run_skill(request: SkillRunRequest):
    """独立执行一个 Skill — 生成代码并可选执行

    这是模块化设计的核心端点：用户选择一个可视化 Skill，
    传入数据和参数，即可独立生成图表，不依赖完整建模流程。
    """
    # 1. 加载 Skill
    skill = skill_manager.get_skill(request.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {request.skill_id}")

    # 2. 构建用户消息
    user_message = _build_user_prompt(request.skill_id, request.params)

    # 3. 创建 LLM 实例
    try:
        from app.utils.llm_config import load_llm_config
        llm_cfg = load_llm_config(skill.agent_type)
        llm_config_dict = {
            "apiKey": llm_cfg.api_key,
            "baseUrl": llm_cfg.base_url,
            "modelId": llm_cfg.model,
            "apiType": llm_cfg.api_type,
        }
        llm = LLMFactory.create_from_config(llm_config_dict)
    except Exception as e:
        logger.error(f"LLM 创建失败: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 创建失败，请检查 API Key 配置是否正确: {str(e)}")

    # 4. 调用 LLM 生成代码
    try:
        messages = [
            {"role": "system", "content": skill.system_prompt},
            {"role": "user", "content": user_message},
        ]
        resp = await llm.chat(messages, max_tokens=2000)
        code = resp.get("content", "")
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 调用失败: {str(e)}")

    # 5. 提取代码块
    if request.skill_id.startswith("flow-"):
        # Mermaid 代码提取
        import re
        m = re.search(r"```mermaid\s*\n(.*?)```", code, re.DOTALL)
        mermaid_code = m.group(1).strip() if m else code
        return SkillRunResponse(
            skill_id=request.skill_id,
            skill_name=skill.name,
            code="",
            language="mermaid",
            mermaid=mermaid_code,
        )
    else:
        # Python 代码提取
        import re
        m = re.search(r"```python\s*\n(.*?)```", code, re.DOTALL)
        python_code = m.group(1).strip() if m else code

        # 6. 可选执行
        execution_result = None
        if request.execute:
            execution_result = await _execute_code_safe(python_code, request.language)

        return SkillRunResponse(
            skill_id=request.skill_id,
            skill_name=skill.name,
            code=python_code,
            language=request.language,
            execution_result=execution_result,
        )


@router.post("/skills/pipeline")
async def run_chart_pipeline(request: ChartPipelineRequest):
    """图表管线 — 串联执行多个 Skill

    支持顺序执行和并行执行两种模式。
    所有 Skill 执行完毕后汇总结果。
    """
    if not request.pipeline:
        raise HTTPException(status_code=400, detail="pipeline 不能为空")

    results = []

    if request.parallel:
        # 并行执行
        async def _run_one(item: Dict[str, Any]):
            try:
                req = SkillRunRequest(
                    skill_id=item["skill_id"],
                    params=item.get("params", {}),
                    execute=request.execute,
                    language=request.language,
                )
                return await run_skill(req)
            except Exception as e:
                return {"skill_id": item["skill_id"], "error": str(e)}

        tasks = [_run_one(item) for item in request.pipeline]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for r in raw_results:
            if isinstance(r, Exception):
                results.append({"error": str(r)})
            elif hasattr(r, 'dict'):
                results.append(r.dict())
            elif isinstance(r, dict):
                results.append(r)
            else:
                results.append({"error": f"Unknown result type: {type(r)}"})
    else:
        # 顺序执行
        for item in request.pipeline:
            try:
                req = SkillRunRequest(
                    skill_id=item["skill_id"],
                    params=item.get("params", {}),
                    execute=request.execute,
                    language=request.language,
                )
                result = await run_skill(req)
                results.append(result.dict() if hasattr(result, 'dict') else result)
            except Exception as e:
                results.append({"skill_id": item["skill_id"], "error": str(e)})

    return {
        "total": len(request.pipeline),
        "success_count": sum(1 for r in results if isinstance(r, dict) and "error" not in r),
        "results": results,
    }
