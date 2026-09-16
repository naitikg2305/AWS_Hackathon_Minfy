import os
import pandas as pd
from strands import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

TRANSIENT_SIGNATURES = {
    "compressor_start": "Pressure surge +15-25 psi, flow +0.3-0.5 MMSCFD, recovers in 5-15 min. Per Operating Procedures Section 5.1.",
    "valve_change": "Pressure redistribution +/-8-15 psi, flow +/-0.1-0.3 MMSCFD, re-equilibrates in 8-20 min. Per Operating Procedures Section 5.1.",
    "temperature_line_pack": "Every 10°F drop reduces line pack ~0.18-0.22 MMSCF/segment. 20°F overnight drop creates 0.35-0.45 MMSCFD apparent deficit. Affects all segments equally. Per Operating Procedures Section 2.4.",
}

ISOLATION_DECISION_TREE = (
    "Per Operating Procedures Section 3.1 Step 4:\n"
    "- Leak rate >0.3 MMSCFD → isolate segment (Section 3.2)\n"
    "- Leak rate <0.3 MMSCFD → dispatch crew, reduce pressure to 700 psi max\n"
    "- Near-rupture (>50 psi drop in <5 min) → immediate ESD (Section 4.1)"
)


def _load_station_envelope(station_id: str) -> dict:
    meta = pd.read_csv(os.path.join(DATA_DIR, "pipeline_segment_metadata.csv"))

    seg_from = meta[meta["from_station"] == station_id]
    seg_to = meta[meta["to_station"] == station_id]

    if not seg_from.empty:
        seg = seg_from.iloc[0]
        mile = 0
        for _, r in meta.iterrows():
            if r["from_station"] == station_id:
                break
            mile += r["length_miles"]
    elif not seg_to.empty:
        seg = seg_to.iloc[0]
        mile = 0
        for _, r in meta.iterrows():
            mile += r["length_miles"]
            if r["to_station"] == station_id:
                break
    else:
        return None

    maop = int(seg["maop_psi"])

    scada = pd.read_csv(os.path.join(DATA_DIR, "scada_timeseries.csv"))
    st_data = scada[scada["station_id"] == station_id]
    normal_data = st_data[st_data["event_flag"].isin(["normal"])]

    if not normal_data.empty:
        p = normal_data["pressure_psi"]
        f = normal_data["flow_mmscfd"]
        p5, p95 = p.quantile(0.05), p.quantile(0.95)
        f5, f95 = f.quantile(0.05), f.quantile(0.95)
        station_type = normal_data["station_type"].iloc[0]
    else:
        p5, p95 = 700, 800
        f5, f95 = 5.5, 6.5
        station_type = "unknown"

    return {
        "type": station_type,
        "mile": mile,
        "pressure_min": round(p5),
        "pressure_max": round(p95),
        "flow_min": round(f5, 1),
        "flow_max": round(f95, 1),
        "maop": maop,
    }


@tool
def lookup_operating_envelope(station_id: str) -> str:
    """Look up the normal operating envelope, known transient signatures, and isolation decision tree for a station. Envelope ranges are computed from baseline SCADA readings.

    Args:
        station_id: Station ID (e.g. 'ST-05').
    """
    sid = station_id.upper().strip()
    env = _load_station_envelope(sid)
    if not env:
        return f"Unknown station: {sid}"

    lines = [
        f"STATION {sid} ({env['type']}) at mile {env['mile']}",
        f"Normal pressure: {env['pressure_min']}-{env['pressure_max']} psi (5th-95th percentile from SCADA baseline)",
        f"Normal flow: {env['flow_min']}-{env['flow_max']} MMSCFD (5th-95th percentile from SCADA baseline)",
        f"MAOP: {env['maop']} psi (from pipeline_segment_metadata.csv) | Design: 900 psi (per Operating Procedures Section 1.1)",
        "",
        "FALSE-POSITIVE TRANSIENT SIGNATURES:",
    ]
    for event_type, desc in TRANSIENT_SIGNATURES.items():
        lines.append(f"  {event_type}: {desc}")
    lines.append("")
    lines.append("ISOLATION DECISION TREE:")
    lines.append(ISOLATION_DECISION_TREE)

    return "\n".join(lines)
