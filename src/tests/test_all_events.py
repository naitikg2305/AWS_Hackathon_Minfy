"""Full 20-event validation: 5 real leaks + 15 false positives via LiveToolAdapter."""
import pandas as pd
import pytest
from pathlib import Path

from src.app.adapters.live_agent import LiveToolAdapter
from src.app.models.investigation import Classification, Status

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

adapter = LiveToolAdapter()


def _load_leaks():
    df = pd.read_csv(DATA_DIR / "labeled_leak_events.csv")
    segments = pd.read_csv(DATA_DIR / "pipeline_segment_metadata.csv")
    events = []
    for _, row in df.iterrows():
        seg = row["affected_segment"]
        seg_row = segments[segments["segment_id"] == seg].iloc[0]
        onset = pd.Timestamp(row["onset_timestamp"])
        events.append({
            "event_id": row["event_id"],
            "station_id": seg_row["from_station"],
            "start": (onset - pd.Timedelta(minutes=15)).isoformat(),
            "end": (onset + pd.Timedelta(minutes=30)).isoformat(),
            "segment": seg,
            "severity": row["severity"],
            "mile_marker": row["true_leak_location_mile_marker"],
        })
    return events


def _load_fps():
    df = pd.read_csv(DATA_DIR / "labeled_false_positive_events.csv")
    events = []
    for _, row in df.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        events.append({
            "event_id": row["event_id"],
            "station_id": row["station_id"],
            "start": (ts - pd.Timedelta(hours=1)).isoformat(),
            "end": (ts + pd.Timedelta(minutes=30)).isoformat(),
            "fp_type": row["fp_type"],
        })
    return events


LEAKS = _load_leaks()
FPS = _load_fps()


@pytest.mark.parametrize("leak", LEAKS, ids=[l["event_id"] for l in LEAKS])
def test_leak_detected(leak):
    result = adapter.investigate_event(
        leak["event_id"], leak["station_id"], leak["start"], leak["end"]
    )
    assert result.status == Status.COMPLETED, f"{leak['event_id']}: status={result.status}"
    assert result.classification == Classification.LIKELY_LEAK, (
        f"{leak['event_id']}: classified as {result.classification.value}, expected LIKELY_LEAK"
    )
    assert result.confidence >= 0.7, f"{leak['event_id']}: confidence {result.confidence} < 0.7"
    assert result.severity is not None, f"{leak['event_id']}: severity is None"
    assert len(result.citations) > 0, f"{leak['event_id']}: no citations"


@pytest.mark.parametrize("leak", LEAKS, ids=[l["event_id"] for l in LEAKS])
def test_leak_has_location(leak):
    result = adapter.investigate_event(
        leak["event_id"], leak["station_id"], leak["start"], leak["end"]
    )
    assert result.estimated_location is not None, f"{leak['event_id']}: no location estimate"
    assert result.affected_segment == leak["segment"], (
        f"{leak['event_id']}: segment {result.affected_segment} != {leak['segment']}"
    )


@pytest.mark.parametrize("fp", FPS, ids=[f["event_id"] for f in FPS])
def test_fp_rejected(fp):
    result = adapter.investigate_event(
        fp["event_id"], fp["station_id"], fp["start"], fp["end"]
    )
    assert result.status == Status.COMPLETED, f"{fp['event_id']}: status={result.status}"
    assert result.classification == Classification.FALSE_POSITIVE, (
        f"{fp['event_id']}: classified as {result.classification.value}, expected FALSE_POSITIVE"
    )
    assert result.severity is None, f"{fp['event_id']}: severity should be None for FP"
    assert result.estimated_location is None, f"{fp['event_id']}: location should be None for FP"


def test_overall_accuracy():
    """At least 90% of all 20 events must be correctly classified."""
    correct = 0
    total = len(LEAKS) + len(FPS)

    for leak in LEAKS:
        r = adapter.investigate_event(leak["event_id"], leak["station_id"], leak["start"], leak["end"])
        if r.classification == Classification.LIKELY_LEAK:
            correct += 1

    for fp in FPS:
        r = adapter.investigate_event(fp["event_id"], fp["station_id"], fp["start"], fp["end"])
        if r.classification == Classification.FALSE_POSITIVE:
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.90, f"Overall accuracy {accuracy:.0%} ({correct}/{total}) below 90% threshold"
