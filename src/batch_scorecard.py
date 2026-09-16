"""Batch scorecard: run all 20 labeled events through tool-based classification and compare to ground truth.

Usage:
    python -m src.batch_scorecard          # print scorecard
    python -m src.batch_scorecard --json   # output as JSON
"""
import sys
import os
import json
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SEGMENT_STATIONS = {
    "SEG-01": ("ST-01", "ST-02"), "SEG-02": ("ST-02", "ST-03"),
    "SEG-03": ("ST-03", "ST-04"), "SEG-04": ("ST-04", "ST-05"),
    "SEG-05": ("ST-05", "ST-06"), "SEG-06": ("ST-06", "ST-07"),
    "SEG-07": ("ST-07", "ST-08"),
}


def classify_event(station_id, timestamp, segment_id=None, reported_rate=0.0):
    """Classify an event using tool logic directly. Returns (classification, confidence_pct, reasons)."""
    ts = pd.Timestamp(timestamp)

    scada = pd.read_csv(os.path.join(DATA_DIR, "scada_timeseries.csv"), parse_dates=["timestamp"])
    window_start = ts - pd.Timedelta(hours=2)
    window_end = ts + pd.Timedelta(hours=1)
    window = scada[(scada["station_id"] == station_id) & (scada["timestamp"] >= window_start) & (scada["timestamp"] <= window_end)]

    comp_starts = (window["event_flag"] == "compressor_start").sum()
    valve_changes = (window["event_flag"] == "valve_change").sum()

    weather = pd.read_csv(os.path.join(DATA_DIR, "weather_conditions.csv"), parse_dates=["timestamp"])
    w = weather[(weather["timestamp"] >= window_start - pd.Timedelta(hours=6)) & (weather["timestamp"] <= window_end)]
    temp_drop = (w["ambient_temp_f"].max() - w["ambient_temp_f"].min()) if len(w) >= 2 else 0

    mbd = window["mass_balance_deficit_mmscfd"] if not window.empty else pd.Series(dtype=float)
    readings_above = (mbd > 0.15).sum() if not mbd.empty else 0
    total_readings = len(mbd)
    mean_deficit = mbd.mean() if not mbd.empty else 0

    checks_clear = 0
    reasons = []
    if comp_starts == 0:
        checks_clear += 1
    else:
        reasons.append(f"compressor_start ({comp_starts} readings)")
    if valve_changes == 0:
        checks_clear += 1
    else:
        reasons.append(f"valve_change ({valve_changes} readings)")
    if temp_drop < 15:
        checks_clear += 1
    else:
        reasons.append(f"temp_drop {temp_drop:.1f}°F")

    has_operational_cause = comp_starts > 0 or valve_changes > 0
    has_temp_cause = temp_drop >= 15 and readings_above < 3
    has_sustained_deficit = readings_above >= 3 and mean_deficit > 0.10

    if has_sustained_deficit and not has_operational_cause:
        classification = "LEAK"
        base_confidence = 85
        if reported_rate >= 0.3:
            base_confidence += 10
        if temp_drop >= 15:
            base_confidence -= 10
    elif has_operational_cause:
        classification = "FALSE_POSITIVE"
        base_confidence = 90
        reasons_str = ", ".join(reasons)
    elif has_temp_cause and not has_sustained_deficit:
        classification = "FALSE_POSITIVE"
        base_confidence = 80
    else:
        classification = "FALSE_POSITIVE"
        base_confidence = 75

    confidence = min(base_confidence, 99)

    return classification, confidence, reasons


def run_scorecard():
    leaks = pd.read_csv(os.path.join(DATA_DIR, "labeled_leak_events.csv"))
    fps = pd.read_csv(os.path.join(DATA_DIR, "labeled_false_positive_events.csv"))

    results = []

    for _, row in leaks.iterrows():
        seg = row["affected_segment"]
        upstream_st, _ = SEGMENT_STATIONS.get(seg, (None, None))
        if not upstream_st:
            continue
        classification, confidence, reasons = classify_event(
            upstream_st, row["onset_timestamp"], seg, row["leak_rate_mmscfd"]
        )
        correct = classification == "LEAK"
        results.append({
            "event_id": row["event_id"],
            "ground_truth": "LEAK",
            "predicted": classification,
            "correct": correct,
            "confidence": confidence,
            "severity": row["severity"],
            "leak_rate": row["leak_rate_mmscfd"],
            "segment": seg,
        })

    for _, row in fps.iterrows():
        classification, confidence, reasons = classify_event(
            row["station_id"], row["timestamp"]
        )
        correct = classification == "FALSE_POSITIVE"
        results.append({
            "event_id": row["event_id"],
            "ground_truth": "FALSE_POSITIVE",
            "predicted": classification,
            "correct": correct,
            "confidence": confidence,
            "fp_type": row["fp_type"],
            "station": row["station_id"],
        })

    return results


def print_scorecard(results):
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total * 100

    print("=" * 72)
    print("PIPELINE LEAK DETECTION AGENT — BATCH SCORECARD")
    print("=" * 72)
    print(f"\nACCURACY: {correct}/{total} ({accuracy:.0f}%)\n")

    print(f"{'Event':<8} {'Truth':<16} {'Predicted':<16} {'Conf':>5} {'Result':<8} {'Detail'}")
    print("-" * 72)

    leak_results = [r for r in results if r["ground_truth"] == "LEAK"]
    fp_results = [r for r in results if r["ground_truth"] == "FALSE_POSITIVE"]

    print("REAL LEAKS:")
    for r in leak_results:
        mark = "PASS" if r["correct"] else "FAIL"
        detail = f"{r.get('severity', '')} {r.get('leak_rate', '')} MMSCFD {r.get('segment', '')}"
        print(f"  {r['event_id']:<6} {'LEAK':<16} {r['predicted']:<16} {r['confidence']:>4}% {mark:<8} {detail}")

    print("\nFALSE POSITIVES:")
    for r in fp_results:
        mark = "PASS" if r["correct"] else "FAIL"
        detail = f"{r.get('fp_type', '')} @ {r.get('station', '')}"
        print(f"  {r['event_id']:<6} {'FALSE_POSITIVE':<16} {r['predicted']:<16} {r['confidence']:>4}% {mark:<8} {detail}")

    print("\n" + "=" * 72)

    leak_correct = sum(1 for r in leak_results if r["correct"])
    fp_correct = sum(1 for r in fp_results if r["correct"])
    print(f"LEAK DETECTION:    {leak_correct}/{len(leak_results)}")
    print(f"FP REJECTION:      {fp_correct}/{len(fp_results)}")
    print(f"OVERALL ACCURACY:  {correct}/{total} ({accuracy:.0f}%)")
    avg_conf = sum(r["confidence"] for r in results) / total
    print(f"AVG CONFIDENCE:    {avg_conf:.0f}%")
    print("=" * 72)

    return {"accuracy": accuracy, "correct": correct, "total": total, "results": results}


if __name__ == "__main__":
    results = run_scorecard()
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        print_scorecard(results)
