"""代码手 Agent — 生成并执行求解代码"""

import re
import json
from typing import Any

from .base import BaseAgent


CODER_PROMPT = """你是一位精通数值计算和科学编程的工程师（Coder）。
根据数学模型，生成可执行的求解代码。

## 代码要求
- 使用 Python 编写
- 包含完整的 import 语句
- 包含数据生成或加载逻辑（如果数据不可用，用合理的模拟数据）
- 核心求解算法实现
- 结果可视化（使用 matplotlib，保存到 figures/ 目录）
- 打印关键结果

## 输出格式
1. 先简要说明代码思路
2. 在 ```python ... ``` 代码块中输出完整代码

## 重要
- 代码必须能独立运行
- 不要使用不存在的数据文件
- 图表保存路径使用 "figures/xxx.png"
- 打印结果要清晰有标注"""

CODE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


class CoderAgent(BaseAgent):

    MAX_RETRIES = 3  # 代码执行失败时自动修复次数

    @property
    def system_prompt(self) -> str:
        return CODER_PROMPT

    async def execute(self, **context) -> dict[str, Any]:
        model = context.get("model", {})
        analysis = context.get("analysis", {})
        language = context.get("language", "python")
        sandbox = context.get("sandbox")  # CodeSandbox 实例（可选）

        user_msg = (
            f"请根据以下数学模型生成 {language} 求解代码：\n\n"
            f"## 问题分析\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n\n"
            f"## 数学模型\n{json.dumps(model, ensure_ascii=False, indent=2)}"
        )
        resp = await self.chat(user_msg)

        code = self._extract_code(resp.content)

        # 可选：执行代码并自动修复
        result = None
        if sandbox and code:
            for attempt in range(self.MAX_RETRIES):
                exec_result = await sandbox.run(code, language)
                if exec_result.get("success"):
                    result = exec_result
                    break
                # 修复
                fix_msg = (
                    f"代码执行失败，请修复：\n\n"
                    f"## 错误信息\n{exec_result.get('stderr', '')}\n"
                    f"## 标准输出\n{exec_result.get('stdout', '')}\n\n"
                    f"请输出修复后的完整代码。"
                )
                fix_resp = await self.chat(fix_msg)
                code = self._extract_code(fix_resp.content)
            if result is None:
                result = exec_result  # 最后一次的结果

        return {
            "code": code,
            "language": language,
            "execution_result": result,
        }

    @staticmethod
    def _extract_code(text: str) -> str:
        m = CODE_RE.search(text)
        if m:
            return m.group(1).strip()
        return text.strip()
