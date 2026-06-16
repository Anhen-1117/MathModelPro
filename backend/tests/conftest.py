"""pytest 共享 fixtures"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from app.config import AgentConfig
from app.infrastructure.llm import LLMAdapter
from app.domain.agent.coordinator import CoordinatorAgent
from app.domain.agent.modeler import ModelerAgent
from app.domain.agent.coder import CoderAgent
from app.domain.agent.writer import WriterAgent


@pytest.fixture
def agent_config():
    return AgentConfig(
        api_key="sk-test123",
        base_url="https://api.deepseek.com",
        model_id="deepseek-chat",
    )


@pytest.fixture
def mock_llm():
    """Mock LLMAdapter，返回预设 JSON"""
    llm = MagicMock(spec=LLMAdapter)
    llm.config = AgentConfig(api_key="sk-test")
    llm.chat = AsyncMock()
    return llm


@pytest_asyncio.fixture
async def coordinator(mock_llm):
    return CoordinatorAgent(mock_llm)


@pytest_asyncio.fixture
async def modeler(mock_llm):
    return ModelerAgent(mock_llm)


@pytest_asyncio.fixture
async def coder(mock_llm):
    return CoderAgent(mock_llm)


@pytest_asyncio.fixture
async def writer(mock_llm):
    return WriterAgent(mock_llm)

