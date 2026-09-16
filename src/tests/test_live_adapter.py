from src.app.adapters.live_agent import LiveToolAdapter
from src.app.models.investigation import Classification, Status, Severity, InvestigationResult


adapter = LiveToolAdapter()


def test_live_detects_real_leak_lk002():
    result = adapter.investigate_event("LK-002", "ST-05", "2026-01-04T23:45:00", "2026-01-05T00:30:00")
    assert isinstance(result, InvestigationResult)
    assert result.classification == Classification.LIKELY_LEAK
    assert result.confidence >= 0.8
    assert result.affected_segment == "SEG-05"
    assert result.estimated_location is not None
    assert len(result.citations) > 0


def test_live_detects_fp_compressor_start():
    result = adapter.investigate_event("FP-001", "ST-01", "2025-12-04T06:50:00", "2025-12-04T07:30:00")
    assert result.classification == Classification.FALSE_POSITIVE
    assert result.severity is None
    assert result.estimated_location is None


def test_live_detects_fp_temperature():
    result = adapter.investigate_event("FP-003", "ST-02", "2025-12-11T04:00:00", "2025-12-11T05:30:00")
    assert result.classification == Classification.FALSE_POSITIVE


def test_live_detects_near_rupture_lk005():
    result = adapter.investigate_event("LK-005", "ST-01", "2026-02-23T23:40:00", "2026-02-24T00:30:00")
    assert result.classification == Classification.LIKELY_LEAK
    assert result.severity is not None


def test_live_handles_invalid_station():
    result = adapter.investigate_event("TEST", "ST-99", "2026-01-01T00:00:00", "2026-01-01T01:00:00")
    assert result.status == Status.ERROR or result.classification == Classification.INCONCLUSIVE
