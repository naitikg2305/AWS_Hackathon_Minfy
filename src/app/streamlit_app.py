import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.app.adapters import get_adapter
from src.app.models.investigation import Classification, Status
from src.app.components.alarm_queue import render_alarm_queue
from src.app.components.event_summary import render_event_summary
from src.app.components.evidence_panel import render_evidence_panel
from src.app.components.response_panel import render_response_panel
from src.app.components.scada_chart import render_scada_chart

st.set_page_config(
    page_title="Pipeline Leak Detection Agent",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .leak-badge {
        background-color: #dc3545; color: white; padding: 4px 12px;
        border-radius: 4px; font-weight: bold; font-size: 1.1em;
    }
    .fp-badge {
        background-color: #28a745; color: white; padding: 4px 12px;
        border-radius: 4px; font-weight: bold; font-size: 1.1em;
    }
    .inconclusive-badge {
        background-color: #ffc107; color: black; padding: 4px 12px;
        border-radius: 4px; font-weight: bold; font-size: 1.1em;
    }
    .metric-card {
        background-color: #f8f9fa; border-radius: 8px; padding: 12px;
        border-left: 4px solid #0d6efd; margin-bottom: 8px;
    }
    .decision-support {
        background-color: #fff3cd; border: 1px solid #ffc107;
        border-radius: 4px; padding: 8px 12px; margin: 8px 0;
        font-size: 0.85em; color: #856404;
    }
</style>
""", unsafe_allow_html=True)

if "investigation_result" not in st.session_state:
    st.session_state.investigation_result = None
if "selected_event" not in st.session_state:
    st.session_state.selected_event = None
if "acknowledged" not in st.session_state:
    st.session_state.acknowledged = False

adapter = get_adapter()

selected = render_alarm_queue()

if selected and selected != st.session_state.selected_event:
    st.session_state.selected_event = selected
    st.session_state.acknowledged = False
    st.session_state.investigation_result = None

    with st.spinner(f"Agent is investigating event {selected['event_id']}..."):
        result = adapter.investigate_event(
            event_id=selected["event_id"],
            station_id=selected.get("station_id", ""),
            start_timestamp=selected.get("start_timestamp", ""),
            end_timestamp=selected.get("end_timestamp", ""),
        )
        st.session_state.investigation_result = result
    st.rerun()

result = st.session_state.investigation_result

if result is None:
    st.markdown("## Pipeline Leak Detection & Integrity Agent")
    st.info("Select an event from the alarm queue to begin investigation.")
    st.markdown("""
    **How it works:**
    1. Select a pipeline alarm event from the sidebar
    2. The AI agent investigates the anomaly against SCADA readings, operational context, weather, and integrity data
    3. It classifies the event as a real leak or false positive, showing all evidence and alternatives considered
    4. For confirmed leaks: location estimate, isolation recommendations, and regulatory guidance
    5. Every claim is traced back to specific data rows and document sections
    """)
elif result.status == Status.ERROR:
    st.error(f"Investigation Error: {result.summary}")
    if st.button("Retry Investigation"):
        st.session_state.investigation_result = None
        st.session_state.selected_event = None
        st.rerun()
else:
    render_event_summary(result)
    st.divider()

    col_left, col_right = st.columns([3, 2])
    with col_left:
        render_scada_chart(result)
    with col_right:
        render_evidence_panel(result)

    st.divider()
    render_response_panel(result)
