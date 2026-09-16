import streamlit as st
import os

DEMO_EVENTS = [
    {
        "event_id": "LK-002",
        "label": "LK-002 — Moderate Leak (SEG-05)",
        "type": "leak",
        "station_id": "ST-05",
        "start_timestamp": "2026-01-04T23:45:00",
        "end_timestamp": "2026-01-05T00:30:00",
    },
    {
        "event_id": "FP-001",
        "label": "FP-001 — Compressor Start (ST-01)",
        "type": "false_positive",
        "station_id": "ST-01",
        "start_timestamp": "2025-12-04T06:50:00",
        "end_timestamp": "2025-12-04T07:30:00",
    },
    {
        "event_id": "FP-003",
        "label": "FP-003 — Temp / Line Pack (ST-02)",
        "type": "false_positive",
        "station_id": "ST-02",
        "start_timestamp": "2025-12-11T04:45:00",
        "end_timestamp": "2025-12-11T05:30:00",
    },
]


def render_alarm_queue() -> dict | None:
    with st.sidebar:
        st.markdown("### Alarm Queue")

        mode = os.environ.get("AGENT_MODE", "mock")
        if mode == "mock":
            st.caption("Mode: **Mock** (deterministic demo responses)")
        else:
            st.caption(f"Mode: **{mode}**")

        st.markdown("---")

        selected = None
        for event in DEMO_EVENTS:
            icon = "🔴" if event["type"] == "leak" else "🟢"
            if st.button(
                f"{icon} {event['label']}",
                key=f"btn_{event['event_id']}",
                use_container_width=True,
            ):
                selected = event

        st.markdown("---")
        st.caption("Pipeline: 200 mi, 8 stations, 7 segments")
        st.caption("MAOP: 850 PSI | Diameter: 24 in | Grade: X65")

    return selected
