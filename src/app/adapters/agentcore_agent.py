import os

from src.app.adapters.base import AgentAdapter
from src.app.models.investigation import InvestigationResult


class AgentCoreAdapter(AgentAdapter):
    def __init__(self):
        self.runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN", "")
        self.region = os.environ.get("AWS_REGION", "us-east-1")

    def investigate_event(
        self,
        event_id: str,
        station_id: str,
        start_timestamp: str,
        end_timestamp: str,
    ) -> InvestigationResult:
        raise NotImplementedError(
            "AgentCore not configured — set AGENT_MODE=agentcore "
            "and provide AGENTCORE_RUNTIME_ARN"
        )
