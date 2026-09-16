import pandas as pd
from pathlib import Path
from strands import tool

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_scada_df = None
_weather_df = None
_valve_df = None


def _load_scada():
    global _scada_df
    if _scada_df is None:
        _scada_df = pd.read_csv(
            DATA_DIR / "scada_timeseries.csv", parse_dates=["timestamp"]
        )
    return _scada_df


def _load_weather():
    global _weather_df
    if _weather_df is None:
        _weather_df = pd.read_csv(
            DATA_DIR / "weather_conditions.csv", parse_dates=["timestamp"]
        )
    return _weather_df


def _load_valve_status():
    global _valve_df
    if _valve_df is None:
        _valve_df = pd.read_csv(
            DATA_DIR / "valve_status.csv", parse_dates=["date"]
        )
        # Fix the join gotcha: valve_status uses bare "01" while everything else uses "SEG-01"
        _valve_df["segment_id"] = "SEG-" + _valve_df["segment_id"].astype(str).str.zfill(2)
    return _valve_df


@tool
def check_operational_context(station_id: str, event_time: str) -> dict:
    """
    Check whether an anomaly at a given station/time has an operational explanation.
    Looks for: compressor starts, valve changes, temperature drops.

    Args:
        station_id: e.g. "ST-03"
        event_time: ISO 8601 string, e.g. "2026-01-27T23:55:00"

    Returns:
        dict with operational context and likely explanation (or none)
    """
    scada = _load_scada()
    weather = _load_weather()
    valve = _load_valve_status()

    event_ts = pd.Timestamp(event_time)
    window_start = event_ts - pd.Timedelta(hours=1)
    window_end = event_ts + pd.Timedelta(minutes=30)

    # --- 1. Check compressor status changes ---
    # Use a wider lookback (6 hours) since compressor starts in the labeled data
    # often precede the observed pressure anomaly by several hours
    compressor_lookback = event_ts - pd.Timedelta(hours=6)
    scada_comp_window = scada[
        (scada["station_id"] == station_id)
        & (scada["timestamp"] >= compressor_lookback)
        & (scada["timestamp"] <= window_end)
    ].sort_values("timestamp")

    scada_window = scada[
        (scada["station_id"] == station_id)
        & (scada["timestamp"] >= window_start)
        & (scada["timestamp"] <= window_end)
    ].sort_values("timestamp")

    compressor_changes = []
    if len(scada_comp_window) > 1:
        statuses = scada_comp_window[["timestamp", "compressor_status"]].values
        for i in range(1, len(statuses)):
            if statuses[i][1] != statuses[i - 1][1]:
                compressor_changes.append({
                    "time": str(statuses[i][0]),
                    "from": statuses[i - 1][1],
                    "to": statuses[i][1],
                })

    has_compressor_start = any(
        c["to"] == "running" and c["from"] in ("standby", "shutdown")
        for c in compressor_changes
    )

    # Also check for compressor_start event flags in the wider window
    compressor_flags = scada_comp_window[scada_comp_window["event_flag"] == "compressor_start"]
    if not compressor_flags.empty:
        has_compressor_start = True

    # --- 2. Check valve position changes ---
    # Use wider window (6 hours) for valve changes too — labeled valve_change events
    # can be hours after the actual SCADA valve_change flag
    valve_lookback = event_ts - pd.Timedelta(hours=6)
    scada_valve_window = scada[
        (scada["station_id"] == station_id)
        & (scada["timestamp"] >= valve_lookback)
        & (scada["timestamp"] <= window_end)
    ].sort_values("timestamp")

    valve_positions = scada_valve_window[["timestamp", "valve_position_pct"]].values
    valve_changes_scada = []
    if len(valve_positions) > 1:
        for i in range(1, len(valve_positions)):
            delta = abs(float(valve_positions[i][1]) - float(valve_positions[i - 1][1]))
            if delta > 15:
                valve_changes_scada.append({
                    "time": str(valve_positions[i][0]),
                    "from_pct": round(float(valve_positions[i - 1][1]), 1),
                    "to_pct": round(float(valve_positions[i][1]), 1),
                    "delta_pct": round(delta, 1),
                })

    valve_event_flags = scada_valve_window[scada_valve_window["event_flag"] == "valve_change"]
    has_valve_change = len(valve_changes_scada) > 0 or not valve_event_flags.empty

    # --- 3. Check temperature / line pack ---
    # Look back 12 hours for temperature trends — line pack effects can lag
    weather_window = weather[
        (weather["timestamp"] >= event_ts - pd.Timedelta(hours=12))
        & (weather["timestamp"] <= window_end)
    ].sort_values("timestamp")

    temp_drop = 0.0
    temp_context = {}
    if not weather_window.empty:
        temps = weather_window["ambient_temp_f"]
        temp_drop = float(temps.max() - temps.min())
        temp_context = {
            "ambient_temp_range_f": f"{round(float(temps.min()), 1)} to {round(float(temps.max()), 1)}",
            "temp_drop_f": round(temp_drop, 1),
            "ground_temp_f": round(float(weather_window["ground_temp_f"].mean()), 1),
            "frost_heave_risk": weather_window["frost_heave_risk"].iloc[-1],
        }

    # Temperature-driven line pack effects can happen anytime there's been a
    # significant temp swing in the preceding hours — not just early morning.
    # Use a higher threshold to avoid false matches on real leaks.
    significant_temp_swing = temp_drop > 15

    # Check if line_pack dropped in SCADA (correlates with temperature)
    line_pack_vals = scada_window["line_pack_mmscf"].values
    line_pack_drop = 0.0
    if len(line_pack_vals) > 1:
        line_pack_drop = float(max(line_pack_vals) - min(line_pack_vals))

    has_temp_line_pack = significant_temp_swing and line_pack_drop > 0.03

    # --- 4. Determine likely explanation ---
    explanations = []
    if has_compressor_start:
        explanations.append({
            "type": "compressor_start",
            "confidence": "high",
            "detail": f"Compressor status change detected at {station_id}. Pressure transients from compressor starts typically cause 10-15 PSI drops lasting 10-20 minutes.",
            "changes": compressor_changes,
        })
    if has_valve_change:
        explanations.append({
            "type": "valve_change",
            "confidence": "high",
            "detail": f"Significant valve position change at {station_id}. Valve adjustments cause pressure redistribution that mimics leak signatures.",
            "changes": valve_changes_scada,
        })
    if has_temp_line_pack:
        explanations.append({
            "type": "temperature_line_pack",
            "confidence": "medium",
            "detail": f"Temperature dropped {temp_drop:.1f}F in the preceding hours. Cold conditions cause gas contraction and line pack reduction, mimicking leak pressure/flow signatures.",
            "temp_context": temp_context,
            "line_pack_drop_mmscf": round(line_pack_drop, 4),
        })

    has_operational_cause = len(explanations) > 0

    return {
        "station_id": station_id,
        "event_time": event_time,
        "has_operational_cause": has_operational_cause,
        "likely_false_positive": has_operational_cause,
        "explanations": explanations,
        "compressor": {
            "start_detected": has_compressor_start,
            "changes": compressor_changes,
        },
        "valve": {
            "change_detected": has_valve_change,
            "changes": valve_changes_scada,
        },
        "temperature": {
            "line_pack_effect": has_temp_line_pack,
            **temp_context,
        },
    }


if __name__ == "__main__":
    import json

    # Test real leak — should find NO operational cause
    print("=== LK-003 (real leak, ST-03):")
    r1 = check_operational_context("ST-03", "2026-01-28T00:00:00")
    print(json.dumps(r1, indent=2, default=str))
    print()

    # Test FP-001 — compressor start
    print("=== FP-001 (compressor_start, ST-01):")
    r2 = check_operational_context("ST-01", "2025-12-04T07:00:00")
    print(json.dumps(r2, indent=2, default=str))
    print()

    # Test FP-003 — temperature line pack
    print("=== FP-003 (temperature_line_pack, ST-02):")
    r3 = check_operational_context("ST-02", "2025-12-11T05:00:00")
    print(json.dumps(r3, indent=2, default=str))
