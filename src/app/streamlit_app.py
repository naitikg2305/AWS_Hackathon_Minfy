import hmac
import inspect
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.app.adapters import get_adapter
from src.app.models.investigation import Classification, InvestigationResult, Status
from src.app.components.alarm_queue import render_alarm_queue
from src.app.components.event_summary import render_event_summary
from src.app.components.evidence_panel import render_evidence_panel
from src.app.components.response_panel import render_response_panel
from src.app.components.scada_chart import render_scada_chart
from src.app.components.pipeline_map import render_pipeline_map
from src.app.components.scorecard import render_scorecard
from src.app.components.confidence_panel import render_confidence_panel
from src.app.components.scenario_panel import render_scenario_panel

st.set_page_config(
    page_title="Pipeline Leak Detection Agent",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Streamlit's fixed header is ~3.75rem tall; too little top padding hides the page title under it */
    .block-container { padding-top: 4rem; padding-bottom: 0.5rem; }
    h1 { line-height: 1.2; padding-top: 0; }
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

# Optional shared-password gate for the public demo host. Unset APP_PASSWORD = open access (local dev).
_APP_PASSWORD = os.environ.get("APP_PASSWORD")
if _APP_PASSWORD and not st.session_state.get("authed"):
    st.markdown("<div style='height: 18vh'></div>", unsafe_allow_html=True)
    _, gate, _ = st.columns([1, 1.2, 1])
    with gate:
        st.markdown(
            "<h1 style='text-align:center; margin-bottom:0'>🛢️ Pipeline Leak Detection Agent</h1>"
            "<p style='text-align:center; color:#888; margin-top:0.25rem'>Minfy demo · enter the access code to continue</p>",
            unsafe_allow_html=True,
        )
        pw = st.text_input("Demo access code", type="password", label_visibility="collapsed",
                           placeholder="Access code")
        if pw and hmac.compare_digest(pw, _APP_PASSWORD):
            st.session_state.authed = True
            st.rerun()
        elif pw:
            st.error("Wrong access code.")
    st.stop()

adapter = get_adapter()

RESULT_CACHE_TTL_S = 2 * 60 * 60  # a full agent run takes ~30 s; share results across visitors for 2 h


@st.cache_resource
def _result_cache() -> dict:
    """Server-wide {event_id: (unix_ts, InvestigationResult)} so repeat clicks are instant."""
    return {}


def _run_investigation(event: dict, force: bool = False) -> "InvestigationResult":
    cache = _result_cache()
    hit = cache.get(event["event_id"])
    if hit and not force and time.time() - hit[0] < RESULT_CACHE_TTL_S:
        st.session_state.result_from_cache_at = hit[0]
        return hit[1]

    status = st.status(
        f"Agent investigating {event['event_id']} — live run usually takes 25–40 s "
        "(6 tool calls + Bedrock reasoning). Streaming its analysis below:",
        expanded=True,
    )
    live = status.empty()
    chunks: list[str] = []

    def _on_delta(text: str) -> None:
        chunks.append(text)
        live.markdown("".join(chunks)[-2500:])

    kwargs = dict(
        event_id=event["event_id"],
        station_id=event.get("station_id", ""),
        start_timestamp=event.get("start_timestamp", ""),
        end_timestamp=event.get("end_timestamp", ""),
    )
    if "on_delta" in inspect.signature(adapter.investigate_event).parameters:
        kwargs["on_delta"] = _on_delta
    result = adapter.investigate_event(**kwargs)
    status.update(label=f"Investigation of {event['event_id']} complete", state="complete", expanded=False)

    if result.status != Status.ERROR:
        cache[event["event_id"]] = (time.time(), result)
    st.session_state.result_from_cache_at = None
    return result


selected = render_alarm_queue()

to_investigate, force_live = None, False
if selected and (
    st.session_state.selected_event is None
    or selected["event_id"] != st.session_state.selected_event.get("event_id")
):
    to_investigate = selected
elif st.session_state.pop("force_live_rerun", False) and st.session_state.selected_event:
    to_investigate, force_live = st.session_state.selected_event, True

if to_investigate:
    st.session_state.selected_event = to_investigate
    st.session_state.acknowledged = False
    st.session_state.investigation_result = None
    st.markdown("# Pipeline Leak Detection & Integrity Agent")
    st.session_state.investigation_result = _run_investigation(to_investigate, force=force_live)
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

    cached_at = st.session_state.get("result_from_cache_at")
    col_note, col_btn = st.columns([5, 1])
    with col_note:
        if cached_at:
            st.caption(
                f"Showing a cached agent result from {time.strftime('%H:%M:%S UTC', time.gmtime(cached_at))}. "
                "Re-run to call the live agent again (~30 s)."
            )
        else:
            st.caption("Live agent result from this session.")
    with col_btn:
        if st.button("Re-run live agent", use_container_width=True):
            st.session_state.force_live_rerun = True
            st.rerun()

    render_pipeline_map(result)

    render_event_summary(result)

    st.markdown("---")

    is_leak = result.classification == Classification.LIKELY_LEAK

    if is_leak:
        tab_analysis, tab_confidence, tab_scenarios, tab_scada, tab_scorecard = st.tabs([
            "Analysis & Response",
            "Confidence Scoring",
            "What-If Scenarios",
            "SCADA Timeline",
            "Evaluation Scorecard",
        ])
    else:
        tab_analysis, tab_confidence, tab_scada, tab_scorecard = st.tabs([
            "Analysis & Response",
            "Confidence Scoring",
            "SCADA Timeline",
            "Evaluation Scorecard",
        ])
        tab_scenarios = None

    with tab_analysis:
        col_evidence, col_response = st.columns([1, 1])

        with col_evidence:
            render_evidence_panel(result)

        with col_response:
            render_response_panel(result)

    with tab_confidence:
        render_confidence_panel(result, st.session_state.selected_event or {})

    if tab_scenarios is not None:
        with tab_scenarios:
            render_scenario_panel(result)

    with tab_scada:
        render_scada_chart(result)

    with tab_scorecard:
        render_scorecard()
