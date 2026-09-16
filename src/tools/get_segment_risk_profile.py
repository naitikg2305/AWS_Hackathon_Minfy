import os
import pandas as pd
from strands import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _normalize_segment_id(sid: str) -> str:
    if not sid.startswith("SEG-"):
        return f"SEG-{sid.zfill(2)}"
    return sid


@tool
def get_segment_risk_profile(segment_id: str) -> str:
    """Get the risk profile for a pipeline segment including metadata, inspection history, cathodic protection status, and nearby encroachments.

    Args:
        segment_id: Pipeline segment ID (e.g. 'SEG-05' or '05').
    """
    seg = _normalize_segment_id(segment_id)

    meta = pd.read_csv(os.path.join(DATA_DIR, "pipeline_segment_metadata.csv"))
    row = meta[meta["segment_id"] == seg]
    if row.empty:
        return f"No segment found for {seg}"
    m = row.iloc[0]

    inspections = pd.read_csv(os.path.join(DATA_DIR, "inspection_history.csv"))
    seg_insp = inspections[inspections["segment_id"] == seg].sort_values("date", ascending=False)
    latest_insp = seg_insp.head(3)

    cp = pd.read_csv(os.path.join(DATA_DIR, "cathodic_protection.csv"))
    seg_cp = cp[cp["segment_id"] == seg].sort_values("date", ascending=False)
    recent_cp = seg_cp.head(30)
    fail_rate = (recent_cp["criteria_met"] == "Fail").mean() * 100 if len(recent_cp) > 0 else 0

    enc = pd.read_csv(os.path.join(DATA_DIR, "row_encroachment.csv"))
    seg_enc = enc[enc["segment_id"] == seg]
    active_enc = seg_enc[seg_enc["status"] != "Closed"]

    max_depth = latest_insp["max_depth_pct_wt"].max() if not latest_insp.empty else 0

    lines = [
        f"SEGMENT: {seg} | {m['from_station']}→{m['to_station']} | {m['length_miles']}mi | {m['diameter_in']}in | {m['material_grade']}",
        f"MAOP: {m['maop_psi']} psi | Valves: {m['valve_locations_mile_markers']}",
        f"INSPECTIONS (latest {len(latest_insp)}): max wall-loss {max_depth:.0f}% WT",
    ]
    for _, i in latest_insp.iterrows():
        lines.append(f"  {i['inspection_id']} {i['date']} {i['inspection_type']}: {i['result']} ({i['anomaly_count']} anomalies, {i['anomaly_type']})")
    lines.append(f"CP: {fail_rate:.0f}% failure rate (last 30 readings)")
    lines.append(f"ENCROACHMENTS: {len(active_enc)} active")
    for _, e in active_enc.iterrows():
        lines.append(f"  {e['encroachment_id']} mile {e['mile_marker']} {e['encroachment_type']} risk={e['risk_level']} {e['distance_from_pipe_ft']}ft from pipe")

    return "\n".join(lines)
