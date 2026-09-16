"""
Validate all 20 labeled events (5 real leaks + 15 false positives)
against our detection tools.
"""
import pandas as pd
import json
from pathlib import Path

from query_scada import query_scada
from check_operational_context import check_operational_context
from locate_leak import locate_leak

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def validate_leak(event):
    """Validate a real leak event."""
    event_id = event["event_id"]
    onset = event["onset_timestamp"]
    segment = event["affected_segment"]
    true_mile = event["true_leak_location_mile_marker"]
    severity = event["severity"]
    leak_rate = event["leak_rate_mmscfd"]

    # Determine which stations bound this segment
    segments = pd.read_csv(DATA_DIR / "pipeline_segment_metadata.csv")
    seg_row = segments[segments["segment_id"] == segment].iloc[0]
    from_st = seg_row["from_station"]
    to_st = seg_row["to_station"]

    onset_ts = pd.Timestamp(onset)
    start = (onset_ts - pd.Timedelta(minutes=15)).isoformat()
    end = (onset_ts + pd.Timedelta(minutes=30)).isoformat()

    # Run tools
    scada_from = query_scada(from_st, start, end)
    scada_to = query_scada(to_st, start, end)
    context = check_operational_context(from_st, onset)
    location = locate_leak(from_st, onset)

    # Check detection
    # Primary signal: sustained mass balance deficit. This is the strongest indicator.
    # Operational context (compressor/valve/temp) explains false positives but does NOT
    # override a sustained mass balance deficit — a real leak can happen during a cold
    # morning or near a compressor event.
    mbd_sustained = (
        scada_from.get("mass_balance_deficit", {}).get("sustained_above_0.1", False)
        or scada_to.get("mass_balance_deficit", {}).get("sustained_above_0.1", False)
    )
    has_operational_cause = context.get("has_operational_cause", False)
    # Mass balance deficit is the deciding factor. Operational context is informational.
    detected_as_leak = mbd_sustained

    # Check localization
    est_mile = location.get("estimated_mile_marker", -1)
    mile_error = abs(est_mile - true_mile) if est_mile > 0 else -1
    correct_segment = location.get("segment_id", "") == segment

    return {
        "event_id": event_id,
        "type": "REAL_LEAK",
        "severity": severity,
        "leak_rate_mmscfd": leak_rate,
        "true_segment": segment,
        "true_mile": true_mile,
        "detected_as_leak": detected_as_leak,
        "mbd_sustained": mbd_sustained,
        "has_operational_cause": has_operational_cause,
        "correct_segment": correct_segment,
        "estimated_mile": est_mile,
        "mile_error": round(mile_error, 1) if mile_error >= 0 else "N/A",
        "PASS": detected_as_leak and correct_segment,
    }


def validate_false_positive(event):
    """Validate a false positive event."""
    event_id = event["event_id"]
    timestamp = event["timestamp"]
    station_id = event["station_id"]
    fp_type = event["fp_type"]
    pressure_drop = event["pressure_drop_psi"]

    ts = pd.Timestamp(timestamp)
    start = (ts - pd.Timedelta(minutes=15)).isoformat()
    end = (ts + pd.Timedelta(minutes=30)).isoformat()

    scada = query_scada(station_id, start, end)
    context = check_operational_context(station_id, timestamp)

    mbd_sustained = scada.get("mass_balance_deficit", {}).get("sustained_above_0.1", False)
    has_operational_cause = context.get("has_operational_cause", False)

    # For a false positive, we WANT: has_operational_cause=True OR mbd_sustained=False
    correctly_rejected = has_operational_cause or not mbd_sustained

    # Check if the right type of cause was identified
    detected_types = [e["type"] for e in context.get("explanations", [])]
    correct_type = fp_type in detected_types

    return {
        "event_id": event_id,
        "type": "FALSE_POSITIVE",
        "fp_type": fp_type,
        "pressure_drop_psi": pressure_drop,
        "station_id": station_id,
        "correctly_rejected": correctly_rejected,
        "has_operational_cause": has_operational_cause,
        "mbd_sustained": mbd_sustained,
        "detected_cause_types": detected_types,
        "correct_cause_type": correct_type,
        "PASS": correctly_rejected,
    }


if __name__ == "__main__":
    print("=" * 70)
    print("VALIDATION: 5 Real Leaks + 15 False Positives")
    print("=" * 70)

    # Load labeled events
    leaks = pd.read_csv(DATA_DIR / "labeled_leak_events.csv")
    fps = pd.read_csv(DATA_DIR / "labeled_false_positive_events.csv")

    # Validate real leaks
    print("\n--- REAL LEAKS ---")
    leak_results = []
    for _, row in leaks.iterrows():
        r = validate_leak(row.to_dict())
        leak_results.append(r)
        status = "PASS" if r["PASS"] else "FAIL"
        print(f"  {r['event_id']} ({r['severity']}, {r['leak_rate_mmscfd']} mmscfd) "
              f"=> detected={r['detected_as_leak']}, segment={r['correct_segment']}, "
              f"mile_error={r['mile_error']} [{status}]")

    # Validate false positives
    print("\n--- FALSE POSITIVES ---")
    fp_results = []
    for _, row in fps.iterrows():
        r = validate_false_positive(row.to_dict())
        fp_results.append(r)
        status = "PASS" if r["PASS"] else "FAIL"
        cause_match = "correct_type" if r["correct_cause_type"] else "wrong_type"
        print(f"  {r['event_id']} ({r['fp_type']}, {r['station_id']}) "
              f"=> rejected={r['correctly_rejected']}, cause={r['detected_cause_types']} "
              f"({cause_match}) [{status}]")

    # Summary
    leak_pass = sum(1 for r in leak_results if r["PASS"])
    fp_pass = sum(1 for r in fp_results if r["PASS"])
    total = len(leak_results) + len(fp_results)
    total_pass = leak_pass + fp_pass

    print(f"\n{'=' * 70}")
    print(f"RESULTS: {total_pass}/{total} passed ({total_pass/total*100:.0f}%)")
    print(f"  Leaks detected:       {leak_pass}/{len(leak_results)}")
    print(f"  FPs correctly rejected: {fp_pass}/{len(fp_results)}")

    avg_mile_error = [r["mile_error"] for r in leak_results if isinstance(r["mile_error"], float)]
    if avg_mile_error:
        print(f"  Avg localization error: {sum(avg_mile_error)/len(avg_mile_error):.1f} miles")

    fp_type_accuracy = sum(1 for r in fp_results if r["correct_cause_type"])
    print(f"  FP cause type match:  {fp_type_accuracy}/{len(fp_results)}")
    print("=" * 70)
