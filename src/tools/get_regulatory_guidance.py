from strands import tool

PHMSA_THRESHOLDS = {
    "gas_volume_mmscf": 3.0,
    "property_damage_usd": 50000,
    "nrc_phone": "1-800-424-8802",
    "nrc_deadline": "within 1 hour of confirmed detection",
    "written_report_deadline": "30 days",
    "form": "PHMSA Form 7100.1",
    "regulation": "49 CFR Part 191",
}


@tool
def get_regulatory_guidance(leak_rate_mmscfd: float, duration_hours: float = 0, has_injury: bool = False, has_fire: bool = False) -> str:
    """Determine PHMSA reporting requirements based on leak parameters. Calculates cumulative gas loss and checks against federal thresholds.

    Args:
        leak_rate_mmscfd: Estimated leak rate in MMSCFD.
        duration_hours: How long the leak has been active (hours). 0 if just detected.
        has_injury: Whether any injury or death has occurred.
        has_fire: Whether fire or explosion has occurred.
    """
    cumulative_mmscf = leak_rate_mmscfd * (duration_hours / 24)
    threshold = PHMSA_THRESHOLDS["gas_volume_mmscf"]

    if leak_rate_mmscfd > 0:
        hours_to_threshold = (threshold / leak_rate_mmscfd) * 24
        days_to_threshold = hours_to_threshold / 24
    else:
        hours_to_threshold = float("inf")
        days_to_threshold = float("inf")

    triggers = []
    if has_injury:
        triggers.append("Injury/death — immediate NRC notification required per 49 CFR 191.5")
    if has_fire:
        triggers.append("Fire/explosion — immediate NRC notification required per 49 CFR 191.5")
    if cumulative_mmscf >= threshold:
        triggers.append(f"Cumulative release {cumulative_mmscf:.2f} MMSCF EXCEEDS {threshold} MMSCF threshold — NRC notification required per 49 CFR 191.5")
    if leak_rate_mmscfd >= 1.0:
        triggers.append("Leak rate >=1.0 MMSCFD — ESD may be required per Operating Procedures Section 4.1")

    lines = [
        f"LEAK RATE: {leak_rate_mmscfd:.2f} MMSCFD | DURATION: {duration_hours:.1f} hrs",
        f"CUMULATIVE RELEASE: {cumulative_mmscf:.2f} MMSCF (threshold: {threshold} MMSCF)",
        f"TIME TO THRESHOLD: {days_to_threshold:.1f} days ({hours_to_threshold:.1f} hrs) at current rate",
        "",
    ]

    if triggers:
        lines.append("REPORTING TRIGGERED:")
        for t in triggers:
            lines.append(f"  - {t}")
    else:
        lines.append("REPORTING: Not yet required. Monitor cumulative release.")
        lines.append(f"  Threshold will be reached in {days_to_threshold:.1f} days at current rate.")

    lines.append("")
    lines.append("IF REPORTING REQUIRED:")
    lines.append(f"  1. Call NRC: {PHMSA_THRESHOLDS['nrc_phone']} ({PHMSA_THRESHOLDS['nrc_deadline']})")
    lines.append(f"  2. File {PHMSA_THRESHOLDS['form']} within {PHMSA_THRESHOLDS['written_report_deadline']}")
    lines.append(f"  3. Regulation: {PHMSA_THRESHOLDS['regulation']}")

    return "\n".join(lines)
