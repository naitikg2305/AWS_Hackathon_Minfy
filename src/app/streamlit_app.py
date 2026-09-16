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
from src.app.components.pipeline_map import render_pipeline_map
from src.app.components.scorecard import render_scorecard

st.set_page_config(
    page_title="Pipeline Leak Detection Agent",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; }
    [data-testid="stMetricValue"] { font-size: 1.3rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 4px 4px 0 0;
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

if selected and (
    st.session_state.selected_event is None
    or selected["event_id"] != st.session_state.selected_event.get("event_id")
):
    st.session_state.selected_event = selected
    st.session_state.acknowledged = False
    st.session_state.investigation_result = None

    with st.spinner(f"Investigating event {selected['event_id']}..."):
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
    st.markdown("# Pipeline Leak Detection & Integrity Agent")
    st.markdown("**AI-Powered Anomaly Triage for SCADA Shift Operators**")

    render_pipeline_map(None)

    st.markdown("---")

    col_about, col_how = st.columns(2)

    with col_about:
        st.markdown("### The Problem")
        st.markdown(
            "A midstream operator manages **200 miles** of natural gas pipeline with "
            "**8 SCADA stations**. When pressure drops or flow changes, it could be a "
            "real leak — or a compressor starting up, a valve moving, or a cold night "
            "shrinking the gas. Distinguishing the two requires contextual reasoning "
            "that rule-based alarms cannot do."
        )
        st.markdown(
            "**Result:** Set thresholds too tight → constant false alarms ($100K+ per shutdown). "
            "Too loose → real leaks go undetected for days (600% cost escalation, $2.7M PHMSA penalties)."
        )

    with col_how:
        st.markdown("### How It Works")
        st.markdown(
            "1. **Select an alarm** from the queue (sidebar)\n"
            "2. The AI agent **investigates** the anomaly against SCADA readings, "
            "operational context, weather, and integrity data\n"
            "3. It **classifies** the event as leak or false positive with evidence\n"
            "4. For confirmed leaks: **location**, **isolation** recommendations, "
            "and **regulatory** guidance\n"
            "5. Every claim **cites** specific data rows and document sections"
        )

    st.markdown("---")
    render_scorecard()

elif result.status == Status.ERROR:
    st.markdown("# Pipeline Leak Detection & Integrity Agent")
    render_pipeline_map(None)
    st.error(f"**Investigation Error:** {result.summary}")
    if st.button("Retry Investigation", type="primary"):
        st.session_state.investigation_result = None
        st.session_state.selected_event = None
        st.rerun()

else:
    st.markdown("# Pipeline Leak Detection & Integrity Agent")

    render_pipeline_map(result)

    render_event_summary(result)

    st.markdown("---")

    tab_analysis, tab_scada, tab_scorecard = st.tabs([
        "Analysis & Response",
        "SCADA Timeline",
        "Evaluation Scorecard",
    ])

    with tab_analysis:
        col_evidence, col_response = st.columns([1, 1])

        with col_evidence:
            render_evidence_panel(result)

        with col_response:
            render_response_panel(result)

    with tab_scada:
        render_scada_chart(result)

    with tab_scorecard:
        render_scorecard()
