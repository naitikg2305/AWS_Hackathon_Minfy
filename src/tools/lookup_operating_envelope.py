from strands import tool

STATION_ENVELOPES = {
    "ST-01": {"type": "compressor", "mile": 0, "pressure_min": 760, "pressure_max": 800, "flow_min": 6.0, "flow_max": 6.5},
    "ST-02": {"type": "meter", "mile": 28, "pressure_min": 745, "pressure_max": 785, "flow_min": 5.9, "flow_max": 6.4},
    "ST-03": {"type": "meter", "mile": 52, "pressure_min": 735, "pressure_max": 775, "flow_min": 5.9, "flow_max": 6.4},
    "ST-04": {"type": "compressor", "mile": 78, "pressure_min": 755, "pressure_max": 795, "flow_min": 5.9, "flow_max": 6.4},
    "ST-05": {"type": "meter", "mile": 104, "pressure_min": 740, "pressure_max": 780, "flow_min": 5.8, "flow_max": 6.3},
    "ST-06": {"type": "custody_transfer", "mile": 130, "pressure_min": 730, "pressure_max": 770, "flow_min": 5.8, "flow_max": 6.3},
    "ST-07": {"type": "meter", "mile": 158, "pressure_min": 720, "pressure_max": 760, "flow_min": 5.7, "flow_max": 6.2},
    "ST-08": {"type": "custody_transfer", "mile": 200, "pressure_min": 710, "pressure_max": 750, "flow_min": 5.7, "flow_max": 6.2},
}

TRANSIENT_SIGNATURES = {
    "compressor_start": "Pressure surge +15-25 psi, flow +0.3-0.5 MMSCFD, recovers in 5-15 min. Per Operating Procedures Section 5.1.",
    "valve_change": "Pressure redistribution +/-8-15 psi, flow +/-0.1-0.3 MMSCFD, re-equilibrates in 8-20 min. Per Operating Procedures Section 5.1.",
    "temperature_line_pack": "Every 10°F drop reduces line pack ~0.18-0.22 MMSCF/segment. 20°F overnight drop creates 0.35-0.45 MMSCFD apparent deficit. Affects all segments equally. Per Operating Procedures Section 2.4.",
}

ISOLATION_DECISION_TREE = (
    "Per Operating Procedures Section 3.1 Step 4:\n"
    "- Leak rate >0.3 MMSCFD → isolate segment (Section 3.2)\n"
    "- Leak rate <0.3 MMSCFD → dispatch crew, reduce pressure to 700 psi max\n"
    "- Near-rupture (>50 psi drop in <5 min) → immediate ESD (Section 4.1)"
)


@tool
def lookup_operating_envelope(station_id: str) -> str:
    """Look up the normal operating envelope, known transient signatures, and isolation decision tree for a station.

    Args:
        station_id: Station ID (e.g. 'ST-05').
    """
    sid = station_id.upper().strip()
    env = STATION_ENVELOPES.get(sid)
    if not env:
        return f"Unknown station: {sid}"

    lines = [
        f"STATION {sid} ({env['type']}) at mile {env['mile']}",
        f"Normal pressure: {env['pressure_min']}-{env['pressure_max']} psi",
        f"Normal flow: {env['flow_min']}-{env['flow_max']} MMSCFD",
        f"MAOP: 850 psi | Design: 900 psi",
        "",
        "FALSE-POSITIVE TRANSIENT SIGNATURES:",
    ]
    for event_type, desc in TRANSIENT_SIGNATURES.items():
        lines.append(f"  {event_type}: {desc}")
    lines.append("")
    lines.append("ISOLATION DECISION TREE:")
    lines.append(ISOLATION_DECISION_TREE)

    return "\n".join(lines)
