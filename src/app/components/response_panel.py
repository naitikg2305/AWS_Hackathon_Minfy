import streamlit as st

from src.app.models.investigation import InvestigationResult, Classification


def render_response_panel(result: InvestigationResult):
    is_leak = result.classification == Classification.LIKELY_LEAK

    col_actions, col_citations = st.columns([1, 1])

    with col_actions:
        st.markdown("### Recommended Actions")
        st.markdown(
            '<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;'
            'padding:8px 14px;margin-bottom:12px;font-size:0.85em;color:#856404;">'
            '⚠️ <strong>DECISION SUPPORT ONLY</strong> — All recommendations require '
            'human review and authorization before action.</div>',
            unsafe_allow_html=True,
        )

        if not is_leak:
            st.markdown(
                '<div style="background:#d4edda;border:1px solid #28a745;border-radius:6px;'
                'padding:10px 14px;margin-bottom:12px;color:#155724;font-weight:bold;">'
                '✓ No emergency response recommended. Continue normal monitoring.</div>',
                unsafe_allow_html=True,
            )

        for action in sorted(result.recommended_actions, key=lambda a: a.priority):
            priority_colors = {1: "#dc3545", 2: "#fd7e14", 3: "#ffc107"}
            color = priority_colors.get(action.priority, "#6c757d")
            if not is_leak:
                color = "#28a745"

            st.markdown(
                f'<div style="border-left:4px solid {color};padding:8px 12px;margin:8px 0;'
                f'background:#f8f9fa;border-radius:0 4px 4px 0;">'
                f'<strong>Priority {action.priority}:</strong> {action.action}<br>'
                f'<span style="font-size:0.8em;color:#6c757d;">Basis: {action.basis}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_citations:
        st.markdown("### Evidence & Citations")

        for i, cite in enumerate(result.citations):
            st.markdown(
                f'<div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;'
                f'padding:10px 14px;margin:6px 0;">'
                f'<strong>📄 {cite.source}</strong><br>'
                f'<code style="font-size:0.85em;">{cite.locator}</code><br>'
                f'<span style="font-size:0.9em;">{cite.claim}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    foot_left, foot_mid, foot_right = st.columns([1, 1, 1])

    with foot_left:
        if result.trace_id:
            st.caption(f"Trace: `{result.trace_id}`")

    with foot_mid:
        st.caption(f"Status: {result.status.value}")

    with foot_right:
        if is_leak:
            if st.session_state.get("acknowledged"):
                st.success("✓ Event Acknowledged")
            else:
                if st.button("Acknowledge Event", type="primary", use_container_width=True):
                    st.session_state.acknowledged = True
                    st.rerun()
        else:
            st.caption("No acknowledgement needed")
