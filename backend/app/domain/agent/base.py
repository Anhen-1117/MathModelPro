"""Agent 基类 — 面向 LLMAdapter 注入"""

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from app.infrastructure.llm import LLMAdapter, LLMResponse


def extract_json(text: str) -> dict:
    """从 LLM 响应中健壮提取 JSON"""
    # 1. 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 2. markdown 代码块
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 3. 首尾 {}
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and s < e:
        try:
            return json.loads(text[s:e + 1])
        except json.JSONDecodeError:
            pass
    # 4. 首尾 []
    s = text.find("[")
    e = text.rfind("]")
    if s != -1 and e != -1 and s < e:
        try:
            return json.loads(text[s:e + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法提取 JSON: {text[:200]}...")


class BaseAgent(ABC):
    """Agent 基类。LLM 通过构造函数注入（依赖反转）。"""

    MAX_HISTORY = 10  # 最多保留 N 轮对话

    def __init__(self, llm: LLMAdapter):
        self.llm = llm
        self.history: list[dict[str, str]] = []
        self._notes: str = ""

    def set_notes(self, notes: str):
        """设置用户特殊要求，会在每次对话的 system prompt 末尾自动附加"""
        self._notes = notes

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Agent 的系统提示词"""
        ...

    async def chat(self, user_message: str) -> LLMResponse:
        """与 LLM 对话，自动管理历史"""
        system = self.system_prompt
        if self._notes:
            system += f"\n\n## 用户特殊要求（必须遵守）\n{self._notes}"
        messages = [
            {"role": "system", "content": system},
            *self.history,
            {"role": "user", "content": user_message},
        ]
        resp = await self.llm.chat(messages)
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": resp.content})
        # 修剪历史
        limit = self.MAX_HISTORY * 2
        if len(self.history) > limit:
            self.history = self.history[-limit:]
        return resp

    def clear(self):
        self.history.clear()

    @abstractmethod
    async def execute(self, **context) -> dict[str, Any]:
        """执行 Agent 核心任务"""
        ...
