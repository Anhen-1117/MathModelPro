"""Skill 管理服务"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from ..models.skill import Skill, SkillCreateRequest, SkillUpdateRequest

# Skill 数据目录（使用绝对路径，避免工作目录变化导致的问题）
_SKILL_DATA_DIR = str(Path(__file__).parent.parent.parent / "data" / "skills")


class SkillManager:
    """Skill 管理器"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or _SKILL_DATA_DIR
        self.skills: Dict[str, Skill] = {}
        self.agent_configs: Dict[str, str] = {}  # agent_type -> skill_id

        os.makedirs(self.data_dir, exist_ok=True)
        self._load_skills()
        self._init_builtin_skills()
    
    def _load_skills(self):
        """从文件加载 Skills（带缓存检查）"""
        skills_file = os.path.join(self.data_dir, "skills.json")
        if os.path.exists(skills_file):
            try:
                with open(skills_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for skill_data in data.get("skills", []):
                        skill = Skill(**skill_data)
                        self.skills[skill.id] = skill
            except Exception:
                pass
        
        configs_file = os.path.join(self.data_dir, "agent_configs.json")
        if os.path.exists(configs_file):
            try:
                with open(configs_file, "r", encoding="utf-8") as f:
                    self.agent_configs = json.load(f)
            except Exception:
                pass
    
    def _save_skills(self):
        """保存 Skills 到文件"""
        skills_file = os.path.join(self.data_dir, "skills.json")
        with open(skills_file, "w", encoding="utf-8") as f:
            json.dump({
                "skills": [skill.dict() for skill in self.skills.values()]
            }, f, ensure_ascii=False, indent=2, default=str)
        
        configs_file = os.path.join(self.data_dir, "agent_configs.json")
        with open(configs_file, "w", encoding="utf-8") as f:
            json.dump(self.agent_configs, f, ensure_ascii=False, indent=2)
    
    def _init_builtin_skills(self):
        """初始化内置 Skills"""
        if not self.skills:
            # 协调器内置 Skill
            self._create_builtin(
                "coordinator-default",
                "协调器默认 Skill",
                "数学建模协调器，负责分析问题和分配任务",
                "coordinator",
                """你是一个数学建模项目的协调器。

你的职责：
1. 分析数学建模问题
2. 制定建模计划
3. 协调其他 Agent 完成任务
4. 监控整体进度

请以结构化的方式输出分析结果。"""
            )
            
            # 建模手内置 Skill
            self._create_builtin(
                "modeler-default",
                "建模手默认 Skill",
                "数学建模专家，负责建立数学模型",
                "modeler",
                """你是一个数学建模专家。

你的职责：
1. 根据问题分析建立数学模型
2. 选择合适的建模方法
3. 推导数学公式
4. 验证模型合理性

常用方法：优化模型、统计模型、机器学习、微分方程、图论、概率模型。"""
            )
            
            # 代码手内置 Skill
            self._create_builtin(
                "coder-default",
                "代码手默认 Skill",
                "程序员，负责编写代码实现",
                "coder",
                """你是一个专业的程序员。

你的职责：
1. 根据数学模型生成代码实现
2. 使用合适的 Python 库（numpy, scipy, matplotlib 等）
3. 生成可运行的完整代码
4. 添加必要的注释

代码规范：使用 Python 3.10+，添加类型提示，处理异常。"""
            )
            
            # 论文手内置 Skill
            self._create_builtin(
                "writer-default",
                "论文手默认 Skill",
                "论文写作专家，负责撰写论文",
                "writer",
                """你是一个专业的数学建模论文写作专家。

你的职责：
1. 根据建模结果撰写完整的论文
2. 使用规范的学术写作格式
3. 包含完整的章节结构
4. 使用 Markdown 格式

论文结构：摘要、问题重述、问题分析、模型假设、符号说明、模型建立与求解、模型检验、模型评价、参考文献。"""
            )
            
            self._save_skills()
    
    def _create_builtin(self, id: str, name: str, desc: str, agent_type: str, prompt: str):
        """创建内置 Skill"""
        skill = Skill(
            id=id,
            name=name,
            description=desc,
            agent_type=agent_type,
            system_prompt=prompt,
            is_builtin=True
        )
        self.skills[id] = skill
    
    # ========== CRUD 操作 ==========
    
    def get_all_skills(self) -> List[Skill]:
        """获取所有 Skills"""
        return list(self.skills.values())
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取单个 Skill"""
        return self.skills.get(skill_id)
    
    def create_skill(self, request: SkillCreateRequest) -> Skill:
        """创建 Skill"""
        skill_id = f"custom-{len(self.skills) + 1}"
        skill = Skill(
            id=skill_id,
            name=request.name,
            description=request.description,
            agent_type=request.agent_type,
            system_prompt=request.system_prompt,
            tools=request.tools,
            config=request.config
        )
        self.skills[skill_id] = skill
        self._save_skills()
        return skill
    
    def update_skill(self, skill_id: str, request: SkillUpdateRequest) -> Optional[Skill]:
        """更新 Skill"""
        skill = self.skills.get(skill_id)
        if not skill:
            return None
        
        if request.name is not None:
            skill.name = request.name
        if request.description is not None:
            skill.description = request.description
        if request.system_prompt is not None:
            skill.system_prompt = request.system_prompt
        if request.tools is not None:
            skill.tools = request.tools
        if request.config is not None:
            skill.config = request.config
        
        skill.updated_at = datetime.now()
        self._save_skills()
        return skill
    
    def delete_skill(self, skill_id: str) -> bool:
        """删除 Skill"""
        skill = self.skills.get(skill_id)
        if not skill or skill.is_builtin:
            return False
        
        del self.skills[skill_id]
        
        # 清理 Agent 配置
        for agent_type, sid in list(self.agent_configs.items()):
            if sid == skill_id:
                del self.agent_configs[agent_type]
        
        self._save_skills()
        return True
    
    # ========== Agent 配置 ==========
    
    def get_agent_skill(self, agent_type: str) -> Optional[Skill]:
        """获取 Agent 当前使用的 Skill"""
        skill_id = self.agent_configs.get(agent_type)
        if skill_id:
            return self.skills.get(skill_id)
        
        # 返回默认 Skill
        default_id = f"{agent_type}-default"
        return self.skills.get(default_id)
    
    def set_agent_skill(self, agent_type: str, skill_id: str) -> bool:
        """设置 Agent 使用的 Skill"""
        if skill_id not in self.skills:
            return False
        
        skill = self.skills[skill_id]
        if skill.agent_type != agent_type and skill.agent_type != "all":
            return False
        
        self.agent_configs[agent_type] = skill_id
        self._save_skills()
        return True
    
    def get_agent_configs(self) -> Dict[str, str]:
        """获取所有 Agent 配置"""
        return self.agent_configs.copy()
    
    # ========== 按类型获取 ==========
    
    def get_skills_by_agent(self, agent_type: str) -> List[Skill]:
        """获取指定 Agent 类型可用的 Skills"""
        return [
            skill for skill in self.skills.values()
            if skill.agent_type == agent_type or skill.agent_type == "all"
        ]


# 全局实例
skill_manager = SkillManager()
