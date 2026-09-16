import streamlit as st

from src.app.models.investigation import InvestigationResult, Classification


def render_response_panel(result: InvestigationResult):
    is_leak = result.classification == Classification.LIKELY_LEAK

    st.markdown("#### Recommended Actions")
    st.markdown(
        '<div class="decision-support">DECISION SUPPORT ONLY — '
        "All recommendations require human review and authorization before action.</div>",
        unsafe_allow_html=True,
    )

    if not is_leak:
        st.success("No emergency response recommended. Continue normal monitoring.")

    for action in sorted(result.recommended_actions, key=lambda a: a.priority):
        icon = "🔴" if action.priority == 1 and is_leak else "🔵"
        st.markdown(f"{icon} **Priority {action.priority}:** {action.action}")
        st.caption(f"Basis: {action.basis}")

    st.markdown("---")

    col_cite, col_trace = st.columns([3, 1])

    with col_cite:
        with st.expander(f"Evidence & Citations ({len(result.citations)} sources)", expanded=False):
            for cite in result.citations:
                st.markdown(f"**{cite.source}** — `{cite.locator}`")
                st.markdown(f"> {cite.claim}")
                st.markdown("")

    with col_trace:
        if result.trace_id:
            st.caption(f"Trace: `{result.trace_id}`")

        if is_leak:
            if st.session_state.get("acknowledged"):
                st.success("Event Acknowledged")
            else:
                if st.button("Acknowledge Event", type="primary"):
                    st.session_state.acknowledged = True
                    st.rerun()
