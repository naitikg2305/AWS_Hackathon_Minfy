import streamlit as st

from src.app.models.investigation import InvestigationResult, Classification


def render_event_summary(result: InvestigationResult):
    is_leak = result.classification == Classification.LIKELY_LEAK
    is_fp = result.classification == Classification.FALSE_POSITIVE

    if is_leak:
        badge_html = '<span style="background:#dc3545;color:#fff;padding:6px 16px;border-radius:6px;font-weight:bold;font-size:1.2em;">⚠ LIKELY LEAK</span>'
    elif is_fp:
        badge_html = '<span style="background:#28a745;color:#fff;padding:6px 16px;border-radius:6px;font-weight:bold;font-size:1.2em;">✓ FALSE POSITIVE</span>'
    else:
        badge_html = '<span style="background:#ffc107;color:#000;padding:6px 16px;border-radius:6px;font-weight:bold;font-size:1.2em;">? INCONCLUSIVE</span>'

    col1, col2, col3, col4, col5 = st.columns([1, 1.5, 1, 1, 1.5])

    with col1:
        st.markdown(f"**Event**")
        st.markdown(f"### {result.event_id}")

    with col2:
        st.markdown("**Classification**")
        st.markdown(badge_html, unsafe_allow_html=True)

    with col3:
        conf_color = "#dc3545" if is_leak else "#28a745" if is_fp else "#ffc107"
        st.markdown("**Confidence**")
        st.markdown(f'<span style="font-size:1.8em;font-weight:bold;color:{conf_color}">{result.confidence:.0%}</span>', unsafe_allow_html=True)

    with col4:
        st.markdown("**Severity**")
        if result.severity:
            sev_text = result.severity.value.replace("_", " ").title()
            sev_colors = {"Seep": "#ffc107", "Moderate": "#fd7e14", "Significant": "#dc3545", "Near Rupture": "#721c24"}
            sev_color = sev_colors.get(sev_text, "#6c757d")
            st.markdown(f'<span style="font-size:1.4em;font-weight:bold;color:{sev_color}">{sev_text}</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="font-size:1.4em;color:#6c757d">N/A</span>', unsafe_allow_html=True)

    with col5:
        st.markdown("**Location**")
        if result.estimated_location and result.affected_segment:
            st.markdown(f"**{result.affected_segment}** — mile {result.estimated_location.mile_marker}")
            st.caption(f"± {result.estimated_location.uncertainty_miles} mi uncertainty")
        elif result.affected_segment:
            st.markdown(f"**{result.affected_segment}**")
        else:
            st.markdown('<span style="color:#6c757d">N/A — no leak detected</span>', unsafe_allow_html=True)

    if is_leak:
        st.error(f"**{result.summary}**")
    elif is_fp:
        st.success(f"**{result.summary}**")
    else:
        st.warning(f"**{result.summary}**")
