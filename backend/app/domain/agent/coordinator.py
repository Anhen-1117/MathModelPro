"""协调器 Agent — 问题分析 + 任务拆解"""

from typing import Any

from .base import BaseAgent, extract_json


COORDINATOR_PROMPT = """你是一位经验丰富的数学建模专家（Coordinator）。
你的任务是对用户提供的数学建模问题进行深入分析，制定建模计划。

请以 JSON 格式输出：
```json
{
  "problem_summary": "问题的一句话总结",
  "problem_type": "问题类型（优化/预测/评价/分类/聚类/方程等）",
  "key_variables": ["变量1", "变量2"],
  "constraints": ["约束1", "约束2"],
  "objectives": ["目标1", "目标2"],
  "modeling_plan": ["步骤1", "步骤2", "步骤3"],
  "data_requirements": "需要什么数据",
  "expected_output": "预期产出"
}
```

要求：
- 分析要有深度，不能泛泛而谈
- 建模计划要具体可执行
- 如果问题信息不足，合理假设补充"""


class CoordinatorAgent(BaseAgent):

    @property
    def system_prompt(self) -> str:
        return COORDINATOR_PROMPT

    async def execute(self, **context) -> dict[str, Any]:
        problem = context.get("problem", "")
        language = context.get("language", "zh-CN")

        user_msg = f"请分析以下数学建模问题（语言：{language}）：\n\n{problem}"
        resp = await self.chat(user_msg)

        try:
            return extract_json(resp.content)
        except ValueError:
            return {
                "problem_summary": "分析失败",
                "problem_type": "未知",
                "key_variables": [],
                "constraints": [],
                "objectives": [],
                "modeling_plan": [resp.content],
                "data_requirements": "待定",
                "expected_output": "待定",
            }
