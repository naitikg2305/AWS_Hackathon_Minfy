import streamlit as st
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def render_scorecard():
    """Render the evaluation scorecard showing all 20 labeled events."""
    st.markdown("### Evaluation Scorecard")
    st.caption("Ground truth: 5 confirmed leaks + 15 confirmed false positives")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Events", "20")
    with col2:
        st.metric("Real Leaks", "5", help="LK-001 through LK-005")
    with col3:
        st.metric("False Positives", "15", help="FP-001 through FP-015")
    with col4:
        st.metric("Target Accuracy", "100%", help="5/5 leaks, 15/15 FPs (per validation)")

    tab_leaks, tab_fps = st.tabs(["Confirmed Leaks", "False Positives"])

    with tab_leaks:
        leaks = pd.read_csv(DATA_DIR / "labeled_leak_events.csv")
        leaks_display = leaks.rename(columns={
            "event_id": "Event",
            "onset_timestamp": "Onset",
            "true_leak_location_mile_marker": "Mile Marker",
            "affected_segment": "Segment",
            "leak_rate_mmscfd": "Rate (MMSCFD)",
            "severity": "Severity",
            "detection_lag_minutes": "Detection Lag (min)",
        })
        st.dataframe(leaks_display, use_container_width=True, hide_index=True)

    with tab_fps:
        fps = pd.read_csv(DATA_DIR / "labeled_false_positive_events.csv")
        fps_display = fps.rename(columns={
            "event_id": "Event",
            "timestamp": "Timestamp",
            "station_id": "Station",
            "fp_type": "FP Type",
            "pressure_drop_psi": "Pressure Drop (PSI)",
            "duration_minutes": "Duration (min)",
            "explanation": "Explanation",
        })
        st.dataframe(fps_display, use_container_width=True, hide_index=True)
