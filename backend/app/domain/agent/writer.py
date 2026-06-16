"""论文手 Agent — 撰写数学建模论文"""

import json
from typing import Any

from .base import BaseAgent


WRITER_PROMPT = """你是一位数学建模竞赛论文写作专家（Writer）。
根据问题分析、数学模型和代码结果，撰写一篇完整的数学建模论文。

## 论文结构
1. **摘要** — 问题背景、方法概述、主要结果（300字以内）
2. **问题重述** — 对原问题的理解和分析
3. **模型假设** — 列出所有模型假设及理由
4. **符号说明** — 所有变量和参数的定义
5. **模型建立与求解** — 核心内容，详细描述建模过程和求解方法
6. **结果分析** — 数值结果、图表分析、灵敏度分析
7. **模型评价与推广** — 优缺点和改进方向
8. **参考文献** — 列出引用的文献

## 格式要求
- 使用 Markdown 格式
- 数学公式使用 LaTeX 格式（$...$ 或 $$...$$）
- 图表位置用 ![](figures/xxx.png) 标记
- 语言要与用户问题一致

## 输出
直接输出完整的 Markdown 论文，不需要 JSON 包裹。"""


class WriterAgent(BaseAgent):

    @property
    def system_prompt(self) -> str:
        return WRITER_PROMPT

    async def execute(self, **context) -> dict[str, Any]:
        analysis = context.get("analysis", {})
        model = context.get("model", {})
        code_result = context.get("code_result", {})
        problem = context.get("problem", "")
        template = context.get("template", "cumcm")

        # 构建丰富的上下文
        sections = [
            f"## 原问题\n{problem}",
            f"## 问题分析\n{json.dumps(analysis, ensure_ascii=False, indent=2)}",
            f"## 数学模型\n{json.dumps(model, ensure_ascii=False, indent=2)}",
        ]
        if code_result and code_result.get("stdout"):
            sections.append(f"## 计算结果\n```\n{code_result['stdout']}\n```")
        if code_result and code_result.get("stderr"):
            sections.append(f"## 运行日志\n```\n{code_result['stderr']}\n```")

        user_msg = (
            f"请根据以下信息撰写数学建模论文（模板：{template}）：\n\n"
            + "\n\n".join(sections)
        )
        resp = await self.chat(user_msg)

        return {
            "paper_content": resp.content,
            "format": "markdown",
        }
