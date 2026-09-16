import re

import streamlit as st

from src.app.models.investigation import InvestigationResult
from src.tools.simulate_scenario import simulate_scenario


def _parse_scenario_output(text: str) -> dict:
    """Parse simulate_scenario text output into structured data."""
    result = {
        "label": "",
        "gas_loss": "",
        "time_to_threshold": "",
        "phmsa_breached": False,
        "gas_cost": "",
        "shutdown_cost": "",
        "total_cost": "",
        "damage_exceeded": False,
        "escalation": [],
        "comparison": [],
    }

    label_match = re.search(r"SCENARIO:\s*(.+)", text)
    if label_match:
        result["label"] = label_match.group(1).strip()

    gas_match = re.search(r"Cumulative gas loss:\s*([\d.]+)\s*MMSCF", text)
    if gas_match:
        result["gas_loss"] = gas_match.group(1)

    time_match = re.search(r"Time to 3 MMSCF threshold:\s*([\d.inf]+)\s*days", text)
    if time_match:
        result["time_to_threshold"] = time_match.group(1)

    result["phmsa_breached"] = "PHMSA gas threshold breached: YES" in text
    result["damage_exceeded"] = "EXCEEDED" in text

    gas_cost_match = re.search(r"Gas loss:\s*\$([\d,]+)", text)
    if gas_cost_match:
        result["gas_cost"] = gas_cost_match.group(1)

    shutdown_match = re.search(r"Shutdown/isolation:\s*\$([\d,]+)", text)
    if shutdown_match:
        result["shutdown_cost"] = shutdown_match.group(1)

    total_match = re.search(r"Total estimated:\s*\$([\d,]+)", text)
    if total_match:
        result["total_cost"] = total_match.group(1)

    for m in re.finditer(r"•\s*(.+)", text):
        result["escalation"].append(m.group(1).strip())

    for m in re.finditer(r"(Isolate in .+|Wait .+|Delay cost:.+)", text):
        result["comparison"].append(m.group(1).strip())

    return result


def _extract_leak_rate(result: InvestigationResult) -> float:
    """Extract MBD max from observation text."""
    for obs in result.observations:
        if "mass balance" in obs.label.lower():
            match = re.search(r"Max\s+([\d.]+)", obs.value)
            if match:
                return float(match.group(1))
    return 0.0


def render_scenario_panel(result: InvestigationResult):
    st.markdown("### What-If Scenario Projections")
    st.caption("Compare outcomes under different response strategies")

    leak_rate = _extract_leak_rate(result)

    if leak_rate <= 0:
        st.info("No measurable leak rate — scenario projections require a positive leak rate.")
        return

    st.markdown(f"**Current leak rate:** {leak_rate:.2f} MMSCFD")

    col_dur, col_esc = st.columns(2)
    with col_dur:
        duration = st.slider("Projection window (hours)", 12, 168, 48, 12)
    with col_esc:
        escalation_rate = st.slider("Escalation rate (MMSCFD)", leak_rate, leak_rate * 5, leak_rate * 2, 0.1)

    scenarios = [
        {"key": "continue", "label": "Continue (no action)", "kwargs": {"current_leak_rate": leak_rate, "scenario": "continue", "duration_hours": duration}},
        {"key": "double", "label": "Rate Doubles", "kwargs": {"current_leak_rate": leak_rate, "scenario": "double", "duration_hours": duration}},
        {"key": "escalate", "label": "Escalates", "kwargs": {"current_leak_rate": leak_rate, "scenario": "escalate", "duration_hours": duration, "new_leak_rate": escalation_rate}},
        {"key": "isolate", "label": "Isolate Now", "kwargs": {"current_leak_rate": leak_rate, "scenario": "isolate", "duration_hours": 1}},
    ]

    with st.spinner("Running scenario projections..."):
        results = []
        for s in scenarios:
            raw = simulate_scenario(**s["kwargs"])
            parsed = _parse_scenario_output(raw)
            parsed["key"] = s["key"]
            parsed["display_label"] = s["label"]
            results.append(parsed)

    cols = st.columns(len(results))
    for col, s in zip(cols, results):
        with col:
            is_isolate = s["key"] == "isolate"
            border_color = "#28a745" if is_isolate else "#dc3545" if s["phmsa_breached"] else "#ffc107"

            st.markdown(
                f'<div style="border:2px solid {border_color};border-radius:8px;padding:12px;'
                f'min-height:280px;background:{"#f0fff0" if is_isolate else "#fff"};">'
                f'<div style="font-weight:bold;font-size:1.1em;margin-bottom:8px;'
                f'color:{border_color};">{s["display_label"]}</div>',
                unsafe_allow_html=True,
            )

            st.metric("Gas Loss", f'{s["gas_loss"]} MMSCF')
            st.metric("Total Cost", f'${s["total_cost"]}')
            st.metric("Days to PHMSA", s["time_to_threshold"])

            if s["phmsa_breached"]:
                st.markdown(
                    '<span style="background:#dc3545;color:#fff;padding:2px 8px;'
                    'border-radius:4px;font-size:0.8em;">PHMSA TRIGGERED</span>',
                    unsafe_allow_html=True,
                )
            if s["damage_exceeded"]:
                st.markdown(
                    '<span style="background:#fd7e14;color:#fff;padding:2px 8px;'
                    'border-radius:4px;font-size:0.8em;">$50K DAMAGE EXCEEDED</span>',
                    unsafe_allow_html=True,
                )

            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Response Escalation Triggers")

    continue_scenario = results[0]
    for esc in continue_scenario["escalation"]:
        if "EMERGENCY" in esc:
            st.error(f"**{esc}**")
        elif "ISOLATION" in esc:
            st.warning(f"**{esc}**")
        elif "NRC" in esc or "PHMSA" in esc:
            st.error(f"**{esc}**")
        else:
            st.info(f"**{esc}**")

    if continue_scenario["comparison"]:
        st.markdown("---")
        st.markdown("#### Cost of Delay")
        for line in continue_scenario["comparison"]:
            if "Delay cost" in line:
                st.markdown(f'**{line}**')
            else:
                st.markdown(f"- {line}")
