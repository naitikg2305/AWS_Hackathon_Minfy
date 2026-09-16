import pandas as pd
from pathlib import Path
from strands import tool

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_scada_df = None


def _load_scada():
    global _scada_df
    if _scada_df is None:
        _scada_df = pd.read_csv(
            DATA_DIR / "scada_timeseries.csv", parse_dates=["timestamp"]
        )
    return _scada_df


@tool
def query_scada(station_id: str, start_time: str, end_time: str) -> dict:
    """
    Pull SCADA readings for a station within a time window.
    Returns an aggregated summary — not raw rows.

    Args:
        station_id: e.g. "ST-03"
        start_time: ISO 8601 string, e.g. "2026-01-27T23:30:00"
        end_time: ISO 8601 string, e.g. "2026-01-28T00:30:00"

    Returns:
        dict with summary stats and key readings
    """
    df = _load_scada()
    start = pd.Timestamp(start_time)
    end = pd.Timestamp(end_time)

    mask = (
        (df["station_id"] == station_id)
        & (df["timestamp"] >= start)
        & (df["timestamp"] <= end)
    )
    window = df[mask].copy()

    if window.empty:
        return {"error": f"No data for {station_id} between {start_time} and {end_time}"}

    operational_flags = window[window["event_flag"].isin(["compressor_start", "valve_change"])]["event_flag"].value_counts().to_dict()

    pressure = window["pressure_psi"]
    flow = window["flow_mmscfd"]
    mbd = window["mass_balance_deficit_mmscfd"]

    pressure_drop = float(pressure.iloc[0] - pressure.min())
    pressure_drop_rate = 0.0
    if len(pressure) > 1:
        min_idx = pressure.idxmin()
        first_idx = pressure.index[0]
        minutes = (window.loc[min_idx, "timestamp"] - window.loc[first_idx, "timestamp"]).total_seconds() / 60
        if minutes > 0:
            pressure_drop_rate = pressure_drop / minutes

    mbd_sustained = bool((mbd.abs() > 0.1).sum() >= 3)
    mbd_max = float(mbd.max())
    mbd_mean = float(mbd.mean())

    first_row = window.iloc[0]
    last_row = window.iloc[-1]

    return {
        "station_id": station_id,
        "time_window": f"{start_time} to {end_time}",
        "readings_count": len(window),
        "pressure": {
            "start_psi": round(float(first_row["pressure_psi"]), 2),
            "end_psi": round(float(last_row["pressure_psi"]), 2),
            "min_psi": round(float(pressure.min()), 2),
            "max_psi": round(float(pressure.max()), 2),
            "drop_psi": round(pressure_drop, 2),
            "drop_rate_psi_per_min": round(pressure_drop_rate, 3),
        },
        "flow": {
            "start_mmscfd": round(float(first_row["flow_mmscfd"]), 4),
            "end_mmscfd": round(float(last_row["flow_mmscfd"]), 4),
            "mean_mmscfd": round(float(flow.mean()), 4),
        },
        "mass_balance_deficit": {
            "max_mmscfd": round(mbd_max, 4),
            "mean_mmscfd": round(mbd_mean, 4),
            "sustained_above_0.1": mbd_sustained,
            "readings_above_0.1": int((mbd.abs() > 0.1).sum()),
        },
        "compressor_status": first_row["compressor_status"],
        "valve_position_pct_start": round(float(first_row["valve_position_pct"]), 1),
        "valve_position_pct_end": round(float(last_row["valve_position_pct"]), 1),
        "operational_events": operational_flags,
    }


if __name__ == "__main__":
    import json
    # Test with LK-003 (real leak on SEG-03)
    result = query_scada("ST-03", "2026-01-27T23:30:00", "2026-01-28T00:30:00")
    print("=== LK-003 (real leak, ST-03):")
    print(json.dumps(result, indent=2))
    print()
    # Test with FP-001 window (false positive, compressor start at ST-01)
    result2 = query_scada("ST-01", "2025-12-04T13:30:00", "2025-12-04T14:30:00")
    print("=== FP-001 (false positive, ST-01):")
    print(json.dumps(result2, indent=2))
