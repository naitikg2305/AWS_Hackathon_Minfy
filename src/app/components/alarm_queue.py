import os
import pandas as pd
from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def _load_all_events() -> list[dict]:
    events = []
    leaks = pd.read_csv(DATA_DIR / "labeled_leak_events.csv")
    for _, row in leaks.iterrows():
        seg = row["affected_segment"]
        segments = pd.read_csv(DATA_DIR / "pipeline_segment_metadata.csv")
        seg_row = segments[segments["segment_id"] == seg]
        station = seg_row.iloc[0]["from_station"] if not seg_row.empty else "ST-01"

        onset = pd.Timestamp(row["onset_timestamp"])
        events.append({
            "event_id": row["event_id"],
            "label": f"{row['event_id']} — {row['severity'].title()} Leak ({seg})",
            "type": "leak",
            "station_id": station,
            "start_timestamp": (onset - pd.Timedelta(minutes=15)).isoformat(),
            "end_timestamp": (onset + pd.Timedelta(minutes=30)).isoformat(),
            "severity": row["severity"],
            "segment": seg,
        })

    fps = pd.read_csv(DATA_DIR / "labeled_false_positive_events.csv")
    for _, row in fps.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        fp_label = row["fp_type"].replace("_", " ").title()
        events.append({
            "event_id": row["event_id"],
            "label": f"{row['event_id']} — {fp_label} ({row['station_id']})",
            "type": "false_positive",
            "station_id": row["station_id"],
            "start_timestamp": (ts - pd.Timedelta(hours=1)).isoformat(),
            "end_timestamp": (ts + pd.Timedelta(minutes=30)).isoformat(),
            "fp_type": row["fp_type"],
        })

    return events


@st.cache_data
def get_all_events():
    return _load_all_events()


def render_alarm_queue() -> dict | None:
    with st.sidebar:
        st.markdown("## Pipeline Leak Detection")
        st.markdown("**Anomaly Triage Console**")

        mode = os.environ.get("AGENT_MODE", "mock")
        mode_labels = {"mock": "Mock (Demo Fixtures)", "live": "Live (Tool Analysis)", "agentcore": "AgentCore"}
        st.caption(f"Agent: **{mode_labels.get(mode, mode)}**")

        st.markdown("---")

        events = get_all_events()
        leaks = [e for e in events if e["type"] == "leak"]
        fps = [e for e in events if e["type"] == "false_positive"]

        st.markdown("### Confirmed Leaks")
        selected = None
        for event in leaks:
            sev = event.get("severity", "")
            icon = {"seep": "🟡", "moderate": "🟠", "significant": "🔴", "near_rupture": "💥"}.get(sev, "🔴")
            if st.button(f"{icon} {event['label']}", key=f"btn_{event['event_id']}", use_container_width=True):
                selected = event

        st.markdown("### False Positives")
        fp_types = {"compressor_start": "⚙️", "valve_change": "🔧", "temperature_line_pack": "🌡️"}
        for event in fps:
            icon = fp_types.get(event.get("fp_type", ""), "🟢")
            if st.button(f"{icon} {event['label']}", key=f"btn_{event['event_id']}", use_container_width=True):
                selected = event

        st.markdown("---")
        st.markdown("#### Pipeline Info")
        st.caption("200 mi | 8 stations | 7 segments")
        st.caption("MAOP: 850 PSI | 24 in | X65")
        st.caption("Data: 2025-12-01 to 2026-02-28")

    return selected
