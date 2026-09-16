import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.app.models.investigation import InvestigationResult, Classification, Severity, Status

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "app" / "fixtures"


@pytest.fixture(params=["confirmed_leak.json", "compressor_fp.json", "temperature_fp.json"])
def fixture_data(request):
    path = FIXTURES_DIR / request.param
    return json.loads(path.read_text())


def test_fixture_validates(fixture_data):
    result = InvestigationResult(**fixture_data)
    assert result.event_id
    assert result.status == Status.COMPLETED
    assert len(result.citations) > 0


def test_confirmed_leak_fixture():
    data = json.loads((FIXTURES_DIR / "confirmed_leak.json").read_text())
    result = InvestigationResult(**data)
    assert result.classification == Classification.LIKELY_LEAK
    assert result.severity == Severity.MODERATE
    assert result.affected_segment == "SEG-05"
    assert result.estimated_location is not None
    assert result.estimated_location.mile_marker == 119.3
    assert len(result.alternatives_considered) == 3
    assert result.integrity_context is not None


def test_compressor_fp_fixture():
    data = json.loads((FIXTURES_DIR / "compressor_fp.json").read_text())
    result = InvestigationResult(**data)
    assert result.classification == Classification.FALSE_POSITIVE
    assert result.severity is None
    assert result.estimated_location is None


def test_temperature_fp_fixture():
    data = json.loads((FIXTURES_DIR / "temperature_fp.json").read_text())
    result = InvestigationResult(**data)
    assert result.classification == Classification.FALSE_POSITIVE
    assert result.confidence == 0.91


def test_invalid_classification_rejected():
    with pytest.raises(ValidationError):
        InvestigationResult(
            event_id="TEST",
            status="completed",
            classification="INVALID",
            confidence=0.5,
            summary="test",
        )


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        InvestigationResult(
            event_id="TEST",
            status="completed",
            classification="LIKELY_LEAK",
            confidence=1.5,
            summary="test",
        )


def test_minimal_valid_result():
    result = InvestigationResult(
        event_id="TEST-001",
        status=Status.COMPLETED,
        classification=Classification.INCONCLUSIVE,
        confidence=0.5,
        summary="Insufficient data for classification.",
    )
    assert result.event_id == "TEST-001"
    assert result.observations == []
    assert result.citations == []
