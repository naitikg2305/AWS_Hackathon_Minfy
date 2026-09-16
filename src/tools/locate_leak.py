import pandas as pd
from pathlib import Path
from strands import tool

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_scada_df = None
_segments_df = None


def _load_scada():
    global _scada_df
    if _scada_df is None:
        _scada_df = pd.read_csv(
            DATA_DIR / "scada_timeseries.csv", parse_dates=["timestamp"]
        )
    return _scada_df


def _load_segments():
    global _segments_df
    if _segments_df is None:
        _segments_df = pd.read_csv(DATA_DIR / "pipeline_segment_metadata.csv")
    return _segments_df


@tool
def locate_leak(station_id: str, event_time: str) -> dict:
    """
    Estimate leak location (mile marker) using pressure gradient between
    the two stations bounding the affected segment.

    Uses the principle: leak is closer to the station with the larger pressure drop.
    Ratio of pressure drops gives proportional distance along the segment.

    Args:
        station_id: Station where anomaly was observed, e.g. "ST-03"
        event_time: ISO 8601 string, e.g. "2026-01-28T00:00:00"

    Returns:
        dict with estimated mile marker, affected segment, nearest valves
    """
    scada = _load_scada()
    segments = _load_segments()
    event_ts = pd.Timestamp(event_time)

    # Find segments where this station is either the from_station or to_station
    seg_from = segments[segments["from_station"] == station_id]
    seg_to = segments[segments["to_station"] == station_id]
    candidate_segments = pd.concat([seg_from, seg_to])

    if candidate_segments.empty:
        return {"error": f"No segment found for station {station_id}"}

    # Get baseline pressure (30 min before event) and event pressure for each candidate
    baseline_start = event_ts - pd.Timedelta(hours=1)
    baseline_end = event_ts - pd.Timedelta(minutes=30)

    results = []
    for _, seg in candidate_segments.iterrows():
        from_st = seg["from_station"]
        to_st = seg["to_station"]
        seg_id = seg["segment_id"]

        # Baseline pressures
        for st in [from_st, to_st]:
            bl = scada[
                (scada["station_id"] == st)
                & (scada["timestamp"] >= baseline_start)
                & (scada["timestamp"] <= baseline_end)
            ]
            ev = scada[
                (scada["station_id"] == st)
                & (scada["timestamp"] >= event_ts)
                & (scada["timestamp"] <= event_ts + pd.Timedelta(minutes=15))
            ]
            if bl.empty or ev.empty:
                continue

        # Get baseline and event pressures for both stations
        bl_from = scada[
            (scada["station_id"] == from_st)
            & (scada["timestamp"] >= baseline_start)
            & (scada["timestamp"] <= baseline_end)
        ]["pressure_psi"].mean()

        bl_to = scada[
            (scada["station_id"] == to_st)
            & (scada["timestamp"] >= baseline_start)
            & (scada["timestamp"] <= baseline_end)
        ]["pressure_psi"].mean()

        ev_from = scada[
            (scada["station_id"] == from_st)
            & (scada["timestamp"] >= event_ts)
            & (scada["timestamp"] <= event_ts + pd.Timedelta(minutes=15))
        ]["pressure_psi"].mean()

        ev_to = scada[
            (scada["station_id"] == to_st)
            & (scada["timestamp"] >= event_ts)
            & (scada["timestamp"] <= event_ts + pd.Timedelta(minutes=15))
        ]["pressure_psi"].mean()

        drop_from = bl_from - ev_from
        drop_to = bl_to - ev_to
        total_drop = drop_from + drop_to

        if total_drop <= 0:
            continue

        # Leak is proportionally closer to the station with larger drop
        # ratio = fraction of segment length from from_station
        ratio = max(0.0, min(1.0, drop_from / total_drop))
        seg_length = seg["length_miles"]

        # Calculate cumulative mile marker
        cumulative_start = segments[segments["segment_id"] < seg_id]["length_miles"].sum()
        estimated_mile = cumulative_start + (ratio * seg_length)

        # Parse valve locations
        valve_markers = [float(v.strip()) for v in str(seg["valve_locations_mile_markers"]).split(",")]
        nearest_valves = sorted(valve_markers, key=lambda v: abs(v - estimated_mile))

        # Find isolation valves (one upstream, one downstream of estimated location)
        upstream_valves = [v for v in valve_markers if v <= estimated_mile]
        downstream_valves = [v for v in valve_markers if v >= estimated_mile]

        results.append({
            "segment_id": seg_id,
            "from_station": from_st,
            "to_station": to_st,
            "segment_length_miles": seg_length,
            "pressure_drop_from_station_psi": round(float(drop_from), 2),
            "pressure_drop_to_station_psi": round(float(drop_to), 2),
            "estimated_mile_marker": round(float(estimated_mile), 1),
            "estimation_method": "pressure_gradient_ratio",
            "nearest_valves_mile_markers": nearest_valves,
            "recommended_isolation": {
                "upstream_valve": f"mile {upstream_valves[-1]}" if upstream_valves else "segment start",
                "downstream_valve": f"mile {downstream_valves[0]}" if downstream_valves else "segment end",
            },
            "segment_maop_psi": int(seg["maop_psi"]),
        })

    if not results:
        return {"error": f"Could not estimate leak location for {station_id} at {event_time}"}

    # Return the segment with the largest total pressure drop (most likely location)
    best = max(results, key=lambda r: r["pressure_drop_from_station_psi"] + r["pressure_drop_to_station_psi"])
    return best


if __name__ == "__main__":
    import json

    # LK-003: real leak at mile 72.0 on SEG-03 (between ST-03 and ST-04)
    print("=== LK-003 (true location: mile 72.0, SEG-03):")
    r = locate_leak("ST-03", "2026-01-28T00:00:00")
    print(json.dumps(r, indent=2))
    print()

    # LK-002: real leak at mile 119.3 on SEG-05 (between ST-05 and ST-06)
    print("=== LK-002 (true location: mile 119.3, SEG-05):")
    r2 = locate_leak("ST-05", "2026-01-05T00:00:00")
    print(json.dumps(r2, indent=2))
    print()

    # LK-005: real leak at mile 13.6 on SEG-01 (between ST-01 and ST-02)
    print("=== LK-005 (true location: mile 13.6, SEG-01):")
    r3 = locate_leak("ST-01", "2026-02-24T00:00:00")
    print(json.dumps(r3, indent=2))
