import json
import time
from pathlib import Path

from src.app.adapters.base import AgentAdapter
from src.app.models.investigation import (
    InvestigationResult,
    Classification,
    Status,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

EVENT_TO_FIXTURE = {
    "LK-002": "confirmed_leak.json",
    "FP-001": "compressor_fp.json",
    "FP-003": "temperature_fp.json",
}


class MockAgentAdapter(AgentAdapter):
    def investigate_event(
        self,
        event_id: str,
        station_id: str,
        start_timestamp: str,
        end_timestamp: str,
    ) -> InvestigationResult:
        time.sleep(1.5)

        fixture_file = EVENT_TO_FIXTURE.get(event_id)
        if fixture_file is None:
            return InvestigationResult(
                event_id=event_id,
                status=Status.ERROR,
                classification=Classification.INCONCLUSIVE,
                confidence=0.0,
                summary=f"No investigation data available for event {event_id}. "
                "This mock adapter only supports: "
                + ", ".join(sorted(EVENT_TO_FIXTURE.keys())),
            )

        path = FIXTURES_DIR / fixture_file
        data = json.loads(path.read_text())
        return InvestigationResult(**data)
