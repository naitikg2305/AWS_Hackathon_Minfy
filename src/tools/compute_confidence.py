import os
import pandas as pd
from strands import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


@tool
def compute_confidence(station_id: str, timestamp: str, segment_id: str, reported_leak_rate: float = 0.0) -> str:
    """Compute a data-driven confidence score for a leak classification. The score is derived entirely from measurable signals, not guessed.

    Args:
        station_id: Station where anomaly was observed (e.g. 'ST-05').
        timestamp: ISO 8601 timestamp of the anomaly.
        segment_id: Affected pipeline segment (e.g. 'SEG-05').
        reported_leak_rate: Estimated leak rate in MMSCFD (0 if unknown).
    """
    ts = pd.Timestamp(timestamp)
    scores = {}
    details = {}

    # --- Signal 1: False-positive checks (0-4 checks clear) ---
    scada = pd.read_csv(os.path.join(DATA_DIR, "scada_timeseries.csv"), parse_dates=["timestamp"])
    window_start = ts - pd.Timedelta(hours=2)
    window_end = ts + pd.Timedelta(hours=1)
    window = scada[(scada["station_id"] == station_id) & (scada["timestamp"] >= window_start) & (scada["timestamp"] <= window_end)]

    comp_starts = (window["event_flag"] == "compressor_start").sum()
    valve_changes = (window["event_flag"] == "valve_change").sum()

    weather = pd.read_csv(os.path.join(DATA_DIR, "weather_conditions.csv"), parse_dates=["timestamp"])
    w = weather[(weather["timestamp"] >= window_start - pd.Timedelta(hours=6)) & (weather["timestamp"] <= window_end)]
    temp_drop = (w["ambient_temp_f"].max() - w["ambient_temp_f"].min()) if len(w) >= 2 else 0

    # Check if deficit is localized (one segment) vs. system-wide (all segments = temp effect)
    other_stations = [s for s in scada["station_id"].unique() if s != station_id]
    system_wide_deficit = False
    if other_stations:
        other_window = scada[
            (scada["station_id"].isin(other_stations))
            & (scada["timestamp"] >= ts - pd.Timedelta(hours=1))
            & (scada["timestamp"] <= ts + pd.Timedelta(minutes=30))
        ]
        if not other_window.empty:
            other_mean_deficit = other_window["mass_balance_deficit_mmscfd"].mean()
            system_wide_deficit = other_mean_deficit > 0.10

    checks_clear = 0
    check_details = []
    if comp_starts == 0:
        checks_clear += 1
        check_details.append("No compressor starts")
    else:
        check_details.append(f"COMPRESSOR START detected ({comp_starts} readings)")
    if valve_changes == 0:
        checks_clear += 1
        check_details.append("No valve changes")
    else:
        check_details.append(f"VALVE CHANGE detected ({valve_changes} readings)")
    if temp_drop < 15:
        checks_clear += 1
        check_details.append(f"Temp drop {temp_drop:.1f}°F (below 15°F threshold)")
    else:
        check_details.append(f"TEMP DROP {temp_drop:.1f}°F (above 15°F threshold)")
    if not system_wide_deficit:
        checks_clear += 1
        check_details.append("Deficit is localized (not system-wide)")
    else:
        check_details.append("SYSTEM-WIDE deficit detected (suggests temperature/line pack, not localized leak)")

    scores["fp_checks"] = checks_clear / 4.0
    details["fp_checks"] = check_details

    # --- Signal 2: Mass balance deficit persistence ---
    if not window.empty:
        mbd = window["mass_balance_deficit_mmscfd"]
        readings_above = (mbd > 0.15).sum()
        total_readings = len(mbd)
        persistence = readings_above / total_readings if total_readings > 0 else 0
        mean_deficit = mbd.mean()
    else:
        persistence = 0
        mean_deficit = 0
        readings_above = 0
        total_readings = 0

    scores["deficit_persistence"] = min(persistence * 1.5, 1.0)
    details["deficit_persistence"] = f"{readings_above}/{total_readings} readings above 0.15 MMSCFD threshold (mean: {mean_deficit:.3f})"

    # --- Signal 3: Leak rate magnitude ---
    if reported_leak_rate >= 2.0:
        rate_score = 1.0
    elif reported_leak_rate >= 0.8:
        rate_score = 0.9
    elif reported_leak_rate >= 0.3:
        rate_score = 0.75
    elif reported_leak_rate >= 0.15:
        rate_score = 0.5
    else:
        rate_score = 0.2

    scores["leak_rate"] = rate_score
    details["leak_rate"] = f"{reported_leak_rate:.2f} MMSCFD"

    # --- Signal 4: Segment integrity risk ---
    seg = segment_id if segment_id.startswith("SEG-") else f"SEG-{segment_id.zfill(2)}"

    cp = pd.read_csv(os.path.join(DATA_DIR, "cathodic_protection.csv"))
    seg_cp = cp[cp["segment_id"] == seg].sort_values("date", ascending=False).head(30)
    cp_fail_rate = (seg_cp["criteria_met"] == "Fail").mean() if len(seg_cp) > 0 else 0

    inspections = pd.read_csv(os.path.join(DATA_DIR, "inspection_history.csv"))
    seg_insp = inspections[inspections["segment_id"] == seg]
    max_wall_loss = seg_insp["max_depth_pct_wt"].max() if not seg_insp.empty else 0
    if pd.isna(max_wall_loss):
        max_wall_loss = 0

    integrity_score = min((cp_fail_rate * 0.5 + (max_wall_loss / 100) * 0.5) * 2, 1.0)
    scores["integrity_risk"] = integrity_score
    details["integrity_risk"] = f"CP fail rate: {cp_fail_rate:.0%}, max wall loss: {max_wall_loss:.0f}% WT"

    # --- Weighted composite score ---
    weights = {"fp_checks": 0.35, "deficit_persistence": 0.25, "leak_rate": 0.25, "integrity_risk": 0.15}
    composite = sum(scores[k] * weights[k] for k in weights)
    pct = int(round(composite * 100))

    if pct >= 85:
        label = "VERY HIGH"
    elif pct >= 70:
        label = "HIGH"
    elif pct >= 50:
        label = "MODERATE"
    elif pct >= 30:
        label = "LOW"
    else:
        label = "VERY LOW"

    lines = [
        f"CONFIDENCE SCORE: {pct}% ({label})",
        "",
        "BREAKDOWN (data-driven, not estimated):",
        f"  FP checks clear:      {scores['fp_checks']:.0%} (weight 35%) — {checks_clear}/4 checks passed",
    ]
    for d in check_details:
        lines.append(f"    • {d}")
    lines.append(f"  Deficit persistence:  {scores['deficit_persistence']:.0%} (weight 25%) — {details['deficit_persistence']}")
    lines.append(f"  Leak rate severity:   {scores['leak_rate']:.0%} (weight 25%) — {details['leak_rate']}")
    lines.append(f"  Segment integrity:    {scores['integrity_risk']:.0%} (weight 15%) — {details['integrity_risk']}")

    return "\n".join(lines)
