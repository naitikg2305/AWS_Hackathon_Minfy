from abc import ABC, abstractmethod

from src.app.models.investigation import InvestigationResult


class AgentAdapter(ABC):
    @abstractmethod
    def investigate_event(
        self,
        event_id: str,
        station_id: str,
        start_timestamp: str,
        end_timestamp: str,
    ) -> InvestigationResult:
        ...
