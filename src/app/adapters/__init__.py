import os

from src.app.adapters.base import AgentAdapter
from src.app.adapters.mock_agent import MockAgentAdapter
from src.app.adapters.agentcore_agent import AgentCoreAdapter


def get_adapter() -> AgentAdapter:
    mode = os.environ.get("AGENT_MODE", "mock")
    if mode == "agentcore":
        return AgentCoreAdapter()
    return MockAgentAdapter()
