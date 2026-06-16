"""V1 Agent 桥接层 — 重新导出到新架构 domain/agent/"""
from app.domain.agent.base import BaseAgent, extract_json
from app.domain.agent.coordinator import CoordinatorAgent
from app.domain.agent.modeler import ModelerAgent
from app.domain.agent.coder import CoderAgent
from app.domain.agent.writer import WriterAgent


class AgentFactory:
    @staticmethod
    def create(agent_type: str, llm):
        mapping = {
            "coordinator": CoordinatorAgent,
            "modeler": ModelerAgent,
            "coder": CoderAgent,
            "writer": WriterAgent,
        }
        return mapping[agent_type](llm)

    @staticmethod
    def create_all(configs: dict):
        return {
            name: AgentFactory.create(name, configs.get(name))
            for name in ["coordinator", "modeler", "coder", "writer"]
        }
