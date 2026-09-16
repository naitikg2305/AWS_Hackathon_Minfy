from src.app.adapters.mock_agent import MockAgentAdapter
from src.app.models.investigation import Classification, Status, InvestigationResult


def test_mock_returns_leak_for_lk002():
    adapter = MockAgentAdapter()
    result = adapter.investigate_event("LK-002", "ST-05", "2026-01-04T23:45:00", "2026-01-05T00:30:00")
    assert isinstance(result, InvestigationResult)
    assert result.classification == Classification.LIKELY_LEAK
    assert result.event_id == "LK-002"


def test_mock_returns_fp_for_fp001():
    adapter = MockAgentAdapter()
    result = adapter.investigate_event("FP-001", "ST-01", "2025-12-04T06:50:00", "2025-12-04T07:30:00")
    assert result.classification == Classification.FALSE_POSITIVE
    assert result.severity is None


def test_mock_returns_fp_for_fp003():
    adapter = MockAgentAdapter()
    result = adapter.investigate_event("FP-003", "ST-02", "2025-12-11T04:45:00", "2025-12-11T05:30:00")
    assert result.classification == Classification.FALSE_POSITIVE


def test_mock_returns_error_for_unknown_event():
    adapter = MockAgentAdapter()
    result = adapter.investigate_event("UNKNOWN-999", "ST-01", "2026-01-01T00:00:00", "2026-01-01T01:00:00")
    assert result.status == Status.ERROR
    assert result.classification == Classification.INCONCLUSIVE
    assert "UNKNOWN-999" in result.summary
