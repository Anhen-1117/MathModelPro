"""测试 BaseAgent — 历史修剪 + LLM 调用"""

import pytest
from unittest.mock import AsyncMock
from app.infrastructure.llm import LLMResponse


@pytest.mark.asyncio
async def test_history_trimming(coordinator):
    """测试超过 MAX_HISTORY 后历史被修剪"""
    # 模拟 LLM 返回内容
    coordinator.llm.chat.return_value = LLMResponse(content="test response")

    # 发送 15 轮对话（超过 MAX_HISTORY=10）
    for i in range(15):
        await coordinator.chat(f"msg {i}")

    # 历史不应超过 10 轮 = 20 条消息
    assert len(coordinator.history) <= 20
    # 最早的应该被裁剪掉了
    assert coordinator.history[0]["content"] != "msg 0"


@pytest.mark.asyncio
async def test_clear_history(coordinator):
    coordinator.history = [{"role": "user", "content": "test"}]
    coordinator.clear()
    assert len(coordinator.history) == 0


@pytest.mark.asyncio
async def test_coordinator_execute_returns_dict(coordinator):
    """测试 CoordinatorAgent 返回结构化 JSON"""
    coordinator.llm.chat.return_value = LLMResponse(
        content='{"problem_summary":"test","problem_type":"optimization","key_variables":["x"],"constraints":[],"objectives":[],"modeling_plan":["step1"],"data_requirements":"none","expected_output":"result"}'
    )
    result = await coordinator.execute(problem="测试问题")
    assert isinstance(result, dict)
    assert "problem_summary" in result
    assert result["problem_type"] == "optimization"


@pytest.mark.asyncio
async def test_coder_extract_code(coder):
    """测试 CoderAgent 代码提取"""
    coder.llm.chat.return_value = LLMResponse(
        content='这是代码说明\n```python\nprint("hello")\n```\n结束'
    )
    result = await coder.execute(model={}, analysis={}, language="python")
    assert "print(\"hello\")" in result["code"]


@pytest.mark.asyncio
async def test_writer_returns_markdown(writer):
    """测试 WriterAgent 返回 Markdown 论文"""
    writer.llm.chat.return_value = LLMResponse(
        content="# 摘要\n\n这是测试论文内容。\n\n## 模型建立\n\n数学公式..."
    )
    result = await writer.execute(analysis={}, model={}, problem="test")
    assert result["format"] == "markdown"
    assert "# 摘要" in result["paper_content"]
