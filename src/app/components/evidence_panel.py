import streamlit as st

from src.app.models.investigation import InvestigationResult, Classification


def render_evidence_panel(result: InvestigationResult):
    is_leak = result.classification == Classification.LIKELY_LEAK

    if is_leak:
        st.markdown("#### Why This Is Likely a Leak")
    else:
        st.markdown("#### Why This Is a False Positive")

    for obs in result.observations:
        st.markdown(f"**{obs.label}**")
        st.markdown(f"> {obs.value}")
        st.caption(f"{obs.station_id} — {obs.timestamp}")

    st.markdown("---")
    st.markdown("#### Alternative Explanations Considered")

    for alt in result.alternatives_considered:
        result_icon = {"ruled_out": "✅", "unlikely": "🟡", "possible": "🔴"}.get(
            alt.result, "⚪"
        )
        with st.expander(f"{result_icon} {alt.cause.replace('_', ' ').title()} — {alt.result.replace('_', ' ')}"):
            st.markdown(alt.reason)

    if result.integrity_context and is_leak:
        st.markdown("---")
        st.markdown("#### Integrity Risk Indicators")

        ic = result.integrity_context
        col1, col2, col3 = st.columns(3)

        with col1:
            risk_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                ic.ili_risk or "", "⚪"
            )
            st.markdown(f"**ILI Risk:** {risk_color} {(ic.ili_risk or 'N/A').title()}")

        with col2:
            cp_color = {"failing": "🔴", "degraded": "🟡", "adequate": "🟢"}.get(
                ic.cp_status or "", "⚪"
            )
            st.markdown(f"**CP Status:** {cp_color} {(ic.cp_status or 'N/A').title()}")

        with col3:
            enc_text = "Yes" if ic.nearby_encroachment else "No"
            enc_color = "🔴" if ic.nearby_encroachment else "🟢"
            st.markdown(f"**Encroachment:** {enc_color} {enc_text}")
