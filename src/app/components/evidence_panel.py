import streamlit as st

from src.app.models.investigation import InvestigationResult, Classification


def render_evidence_panel(result: InvestigationResult):
    is_leak = result.classification == Classification.LIKELY_LEAK

    if is_leak:
        st.markdown("### Why This Is Likely a Leak")
    elif result.classification == Classification.FALSE_POSITIVE:
        st.markdown("### Why This Is a False Positive")
    else:
        st.markdown("### Investigation Observations")

    for obs in result.observations:
        st.markdown(f"**{obs.label}**")
        st.markdown(f"> {obs.value}")
        st.caption(f"📍 {obs.station_id} — {obs.timestamp}")

    st.markdown("---")
    st.markdown("### Alternative Explanations")

    for alt in result.alternatives_considered:
        result_map = {
            "ruled_out": ("✅ Ruled Out", "#28a745"),
            "unlikely": ("🟡 Unlikely", "#ffc107"),
            "possible": ("🟠 Possible", "#fd7e14"),
            "consistent": ("🔴 Consistent", "#dc3545"),
        }
        badge, color = result_map.get(alt.result, ("⚪ Unknown", "#6c757d"))
        cause_name = alt.cause.replace("_", " ").title()

        with st.expander(f"{badge} — {cause_name}", expanded=False):
            st.markdown(alt.reason)

    if result.integrity_context and is_leak:
        st.markdown("---")
        st.markdown("### Integrity Risk Profile")

        ic = result.integrity_context
        c1, c2, c3 = st.columns(3)

        with c1:
            risk_map = {"high": ("🔴", "#dc3545"), "medium": ("🟡", "#ffc107"), "low": ("🟢", "#28a745")}
            icon, color = risk_map.get(ic.ili_risk or "low", ("⚪", "#6c757d"))
            st.markdown(f"**ILI Risk**")
            st.markdown(f'{icon} <span style="color:{color};font-weight:bold">{(ic.ili_risk or "N/A").upper()}</span>', unsafe_allow_html=True)

        with c2:
            cp_map = {"failing": ("🔴", "#dc3545"), "degraded": ("🟡", "#ffc107"), "adequate": ("🟢", "#28a745")}
            icon, color = cp_map.get(ic.cp_status or "adequate", ("⚪", "#6c757d"))
            st.markdown(f"**Cathodic Protection**")
            st.markdown(f'{icon} <span style="color:{color};font-weight:bold">{(ic.cp_status or "N/A").upper()}</span>', unsafe_allow_html=True)

        with c3:
            if ic.nearby_encroachment:
                st.markdown("**Encroachment**")
                st.markdown('🔴 <span style="color:#dc3545;font-weight:bold">ACTIVE NEARBY</span>', unsafe_allow_html=True)
            else:
                st.markdown("**Encroachment**")
                st.markdown('🟢 <span style="color:#28a745;font-weight:bold">NONE</span>', unsafe_allow_html=True)
