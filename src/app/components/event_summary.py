import streamlit as st

from src.app.models.investigation import InvestigationResult, Classification


def render_event_summary(result: InvestigationResult):
    is_leak = result.classification == Classification.LIKELY_LEAK
    is_fp = result.classification == Classification.FALSE_POSITIVE

    if is_leak:
        badge_class = "leak-badge"
        badge_text = "LIKELY LEAK"
    elif is_fp:
        badge_class = "fp-badge"
        badge_text = "FALSE POSITIVE"
    else:
        badge_class = "inconclusive-badge"
        badge_text = "INCONCLUSIVE"

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Event ID", result.event_id)

    with col2:
        st.markdown(f'<span class="{badge_class}">{badge_text}</span>', unsafe_allow_html=True)
        st.caption("Classification")

    with col3:
        st.metric("Confidence", f"{result.confidence:.0%}")

    with col4:
        severity_text = result.severity.value.replace("_", " ").title() if result.severity else "N/A"
        st.metric("Severity", severity_text)

    with col5:
        if result.estimated_location and result.affected_segment:
            loc_text = f"{result.affected_segment}, mile {result.estimated_location.mile_marker}"
            st.metric("Location", loc_text)
            st.caption(f"± {result.estimated_location.uncertainty_miles} mi")
        elif result.affected_segment:
            st.metric("Location", result.affected_segment)
        else:
            st.metric("Location", "N/A")

    if is_leak:
        st.error(f"**Summary:** {result.summary}")
    elif is_fp:
        st.success(f"**Summary:** {result.summary}")
    else:
        st.warning(f"**Summary:** {result.summary}")
