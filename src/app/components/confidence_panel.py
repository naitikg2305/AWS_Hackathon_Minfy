import re

import streamlit as st

from src.app.models.investigation import InvestigationResult, Classification
from src.tools.compute_confidence import compute_confidence


def _parse_confidence_output(text: str) -> dict:
    """Parse the structured text output from compute_confidence into renderable data."""
    result = {"score": 0, "label": "", "signals": [], "details": []}

    score_match = re.search(r"CONFIDENCE SCORE:\s*(\d+)%\s*\((\w[\w ]*)\)", text)
    if score_match:
        result["score"] = int(score_match.group(1))
        result["label"] = score_match.group(2)

    signal_pattern = re.compile(
        r"^\s+([\w\s]+?):\s+(\d+)%\s+\(weight\s+(\d+)%\)\s*—\s*(.+)$", re.MULTILINE
    )
    for m in signal_pattern.finditer(text):
        result["signals"].append({
            "name": m.group(1).strip(),
            "score": int(m.group(2)),
            "weight": int(m.group(3)),
            "detail": m.group(4).strip(),
        })

    bullet_pattern = re.compile(r"^\s+•\s+(.+)$", re.MULTILINE)
    result["details"] = [m.group(1) for m in bullet_pattern.finditer(text)]

    return result


def _score_color(score: int) -> str:
    if score >= 85:
        return "#dc3545"
    if score >= 70:
        return "#fd7e14"
    if score >= 50:
        return "#ffc107"
    return "#28a745"


def render_confidence_panel(result: InvestigationResult, selected_event: dict):
    st.markdown("### Data-Driven Confidence Scoring")
    st.caption("Confidence derived from 4 measurable signals — not LLM-estimated")

    station_id = selected_event.get("station_id", "")
    timestamp = selected_event.get("start_timestamp", "")
    segment_id = result.affected_segment or selected_event.get("segment", "SEG-01")

    leak_rate = 0.0
    if result.observations:
        for obs in result.observations:
            if "mass balance" in obs.label.lower():
                rate_match = re.search(r"Max\s+([\d.]+)", obs.value)
                if rate_match:
                    leak_rate = float(rate_match.group(1))

    with st.spinner("Computing data-driven confidence score..."):
        raw = compute_confidence(
            station_id=station_id,
            timestamp=timestamp,
            segment_id=segment_id,
            reported_leak_rate=leak_rate,
        )

    parsed = _parse_confidence_output(raw)
    score = parsed["score"]
    label = parsed["label"]
    color = _score_color(score)

    col_score, col_comparison = st.columns([1, 2])

    with col_score:
        st.markdown(
            f'<div style="text-align:center;padding:20px;">'
            f'<div style="font-size:4em;font-weight:bold;color:{color};">{score}%</div>'
            f'<div style="font-size:1.3em;font-weight:bold;color:{color};">{label}</div>'
            f'<div style="font-size:0.85em;color:#6c757d;margin-top:8px;">'
            f'Adapter confidence: {result.confidence:.0%}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_comparison:
        for sig in parsed["signals"]:
            sig_color = _score_color(sig["score"])
            st.markdown(
                f'<div style="margin:6px 0;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:2px;">'
                f'<span style="font-weight:bold;">{sig["name"]}</span>'
                f'<span style="color:{sig_color};font-weight:bold;">{sig["score"]}%</span>'
                f'</div>'
                f'<div style="font-size:0.8em;color:#6c757d;">Weight: {sig["weight"]}% — {sig["detail"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.progress(sig["score"] / 100)

    if parsed["details"]:
        st.markdown("---")
        st.markdown("#### False-Positive Check Details")
        for detail in parsed["details"]:
            is_clear = not detail.startswith("COMPRESSOR") and not detail.startswith("VALVE") and not detail.startswith("TEMP DROP") and not detail.startswith("MATCHES")
            icon = "✅" if is_clear else "⚠️"
            st.markdown(f"{icon} {detail}")

    st.markdown("---")
    st.markdown(
        '<div style="background:#e8f4f8;border:1px solid #b8daff;border-radius:6px;'
        'padding:10px 14px;font-size:0.85em;color:#004085;">'
        '<strong>How it works:</strong> Score is a weighted composite of 4 signals — '
        'FP checks clear (35%), MBD persistence (25%), leak rate severity (25%), '
        'and segment integrity risk (15%). Each signal is derived from measured data, '
        'not from LLM inference.</div>',
        unsafe_allow_html=True,
    )
