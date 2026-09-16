"""Edge case and error handling tests."""
import time

import pytest
from pydantic import ValidationError

from src.app.models.investigation import (
    InvestigationResult,
    Classification,
    Severity,
    Status,
)
from src.app.adapters.mock_agent import MockAgentAdapter
from src.app.adapters.live_agent import LiveToolAdapter


# --- Schema edge cases ---

class TestSchemaEdgeCases:
    def test_all_optional_fields_none(self):
        result = InvestigationResult(
            event_id="EDGE-001",
            status=Status.COMPLETED,
            classification=Classification.INCONCLUSIVE,
            confidence=0.5,
            summary="Minimal result with all optional fields as None.",
        )
        assert result.severity is None
        assert result.affected_segment is None
        assert result.estimated_location is None
        assert result.integrity_context is None
        assert result.trace_id is None
        assert result.observations == []
        assert result.citations == []

    def test_confidence_zero_accepted(self):
        result = InvestigationResult(
            event_id="EDGE-002",
            status=Status.ERROR,
            classification=Classification.INCONCLUSIVE,
            confidence=0.0,
            summary="Zero confidence.",
        )
        assert result.confidence == 0.0

    def test_confidence_one_accepted(self):
        result = InvestigationResult(
            event_id="EDGE-003",
            status=Status.COMPLETED,
            classification=Classification.LIKELY_LEAK,
            confidence=1.0,
            severity=Severity.NEAR_RUPTURE,
            summary="Max confidence.",
        )
        assert result.confidence == 1.0

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValidationError):
            InvestigationResult(
                event_id="EDGE-004",
                status=Status.COMPLETED,
                classification=Classification.LIKELY_LEAK,
                confidence=-0.1,
                summary="Negative confidence.",
            )

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            InvestigationResult(
                event_id="EDGE-005",
                status=Status.COMPLETED,
                classification=Classification.LIKELY_LEAK,
                confidence=1.01,
                summary="Over one confidence.",
            )

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValidationError):
            InvestigationResult(
                event_id="EDGE-006",
                status=Status.COMPLETED,
                classification="MAYBE_LEAK",
                confidence=0.5,
                summary="Invalid classification.",
            )

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValidationError):
            InvestigationResult(
                event_id="EDGE-007",
                status=Status.COMPLETED,
                classification=Classification.LIKELY_LEAK,
                confidence=0.9,
                severity="catastrophic",
                summary="Invalid severity.",
            )

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            InvestigationResult(
                event_id="EDGE-008",
                status="pending",
                classification=Classification.INCONCLUSIVE,
                confidence=0.5,
                summary="Invalid status.",
            )

    def test_empty_event_id_accepted(self):
        result = InvestigationResult(
            event_id="",
            status=Status.ERROR,
            classification=Classification.INCONCLUSIVE,
            confidence=0.0,
            summary="Empty event ID.",
        )
        assert result.event_id == ""

    def test_all_severity_values_accepted(self):
        for sev in Severity:
            result = InvestigationResult(
                event_id=f"SEV-{sev.value}",
                status=Status.COMPLETED,
                classification=Classification.LIKELY_LEAK,
                confidence=0.9,
                severity=sev,
                summary=f"Testing {sev.value}.",
            )
            assert result.severity == sev


# --- Adapter edge cases ---

class TestMockAdapterEdgeCases:
    def test_unknown_event_returns_error_status(self):
        adapter = MockAgentAdapter()
        result = adapter.investigate_event("NONEXISTENT", "ST-01", "2026-01-01T00:00:00", "2026-01-01T01:00:00")
        assert result.status == Status.ERROR
        assert result.classification == Classification.INCONCLUSIVE
        assert result.confidence == 0.0

    def test_mock_delay_under_3_seconds(self):
        adapter = MockAgentAdapter()
        start = time.time()
        adapter.investigate_event("LK-002", "ST-05", "2026-01-04T23:45:00", "2026-01-05T00:30:00")
        elapsed = time.time() - start
        assert elapsed < 3.0, f"Mock adapter took {elapsed:.1f}s, expected < 3s"


class TestLiveAdapterEdgeCases:
    def test_graceful_failure_on_invalid_station(self):
        adapter = LiveToolAdapter()
        result = adapter.investigate_event("TEST", "INVALID", "2026-01-01T00:00:00", "2026-01-01T01:00:00")
        assert result.status == Status.ERROR or result.classification == Classification.INCONCLUSIVE

    def test_empty_timestamps_handled(self):
        adapter = LiveToolAdapter()
        result = adapter.investigate_event("TEST", "ST-01", "", "")
        assert result.status in (Status.ERROR, Status.COMPLETED)

    def test_result_always_has_event_id(self):
        adapter = LiveToolAdapter()
        result = adapter.investigate_event("MY-EVENT", "ST-01", "2026-01-01T00:00:00", "2026-01-01T01:00:00")
        assert result.event_id == "MY-EVENT"

    def test_result_always_has_trace_id(self):
        adapter = LiveToolAdapter()
        result = adapter.investigate_event("LK-002", "ST-05", "2026-01-04T23:45:00", "2026-01-05T00:30:00")
        assert result.trace_id is not None
        assert result.trace_id.startswith("live-")
