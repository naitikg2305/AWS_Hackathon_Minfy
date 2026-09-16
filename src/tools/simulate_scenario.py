from strands import tool


@tool
def simulate_scenario(current_leak_rate: float, scenario: str = "continue", duration_hours: float = 48, new_leak_rate: float = 0.0) -> str:
    """Simulate what-if scenarios for a leak event. Calculates projected gas loss, time to regulatory thresholds, cost estimates, and response escalation triggers.

    Args:
        current_leak_rate: Current leak rate in MMSCFD.
        scenario: One of 'continue' (same rate), 'double' (rate doubles), 'escalate' (rate increases to new_leak_rate), 'isolate' (leak stopped after duration_hours).
        duration_hours: Hours to project forward.
        new_leak_rate: New leak rate for 'escalate' scenario (MMSCFD).
    """
    PHMSA_GAS_THRESHOLD = 3.0  # MMSCF
    PHMSA_DAMAGE_THRESHOLD = 50000  # USD
    GAS_COST_PER_MMSCF = 3500  # approximate $/MMSCF at ~$3.50/MCF
    SHUTDOWN_COST_PER_EVENT = 100000
    PHMSA_MAX_PENALTY = 2700000
    ESD_TRIGGER = 1.0  # MMSCFD
    ISOLATION_TRIGGER = 0.3  # MMSCFD

    if scenario == "double":
        rate = current_leak_rate * 2
        label = f"Rate doubles from {current_leak_rate:.2f} to {rate:.2f} MMSCFD"
    elif scenario == "escalate":
        rate = new_leak_rate if new_leak_rate > 0 else current_leak_rate * 1.5
        label = f"Rate escalates from {current_leak_rate:.2f} to {rate:.2f} MMSCFD"
    elif scenario == "isolate":
        rate = current_leak_rate
        label = f"Leak at {rate:.2f} MMSCFD isolated after {duration_hours:.1f} hours"
    else:
        rate = current_leak_rate
        label = f"Leak continues at {rate:.2f} MMSCFD for {duration_hours:.1f} hours"

    if scenario == "isolate":
        total_gas_mmscf = rate * (duration_hours / 24)
    else:
        total_gas_mmscf = rate * (duration_hours / 24)

    gas_cost = total_gas_mmscf * GAS_COST_PER_MMSCF
    total_cost = gas_cost + SHUTDOWN_COST_PER_EVENT

    if rate > 0:
        hours_to_phmsa = (PHMSA_GAS_THRESHOLD / rate) * 24
        days_to_phmsa = hours_to_phmsa / 24
    else:
        hours_to_phmsa = float("inf")
        days_to_phmsa = float("inf")

    hits_phmsa_gas = total_gas_mmscf >= PHMSA_GAS_THRESHOLD
    hits_phmsa_damage = total_cost >= PHMSA_DAMAGE_THRESHOLD

    escalation = []
    if rate >= ESD_TRIGGER:
        escalation.append(f"EMERGENCY SHUTDOWN required — rate {rate:.2f} >= {ESD_TRIGGER} MMSCFD (Operating Procedures Section 4.1)")
    elif rate >= ISOLATION_TRIGGER:
        escalation.append(f"SEGMENT ISOLATION required — rate {rate:.2f} >= {ISOLATION_TRIGGER} MMSCFD (Operating Procedures Section 3.2)")
    else:
        escalation.append(f"MONITOR & DISPATCH CREW — rate {rate:.2f} < {ISOLATION_TRIGGER} MMSCFD (Operating Procedures Section 3.1)")

    if hits_phmsa_gas:
        escalation.append(f"NRC NOTIFICATION REQUIRED — cumulative release {total_gas_mmscf:.2f} MMSCF exceeds 3.0 MMSCF (49 CFR 191.5)")
    if hits_phmsa_damage:
        escalation.append(f"PHMSA FORM 7100.1 TRIGGERED — estimated damage ${total_cost:,.0f} exceeds $50,000 (49 CFR 191.5)")

    lines = [
        f"SCENARIO: {label}",
        "",
        "PROJECTIONS:",
        f"  Cumulative gas loss: {total_gas_mmscf:.2f} MMSCF",
        f"  Time to 3 MMSCF threshold: {days_to_phmsa:.1f} days ({hours_to_phmsa:.1f} hrs)",
        f"  PHMSA gas threshold breached: {'YES' if hits_phmsa_gas else 'NO'}",
        "",
        "COST ESTIMATES:",
        f"  Gas loss: ${gas_cost:,.0f} (at ~$3.50/MCF)",
        f"  Shutdown/isolation: ${SHUTDOWN_COST_PER_EVENT:,.0f}",
        f"  Total estimated: ${total_cost:,.0f}",
        f"  PHMSA damage threshold ($50K): {'EXCEEDED' if hits_phmsa_damage else 'Not reached'}",
        f"  Max PHMSA penalty exposure: ${PHMSA_MAX_PENALTY:,.0f}/violation",
        "",
        "RESPONSE ESCALATION:",
    ]
    for e in escalation:
        lines.append(f"  • {e}")

    if scenario != "isolate":
        lines.append("")
        lines.append("COMPARISON — What if isolated now vs. waiting?")
        gas_now = current_leak_rate * (1 / 24)  # 1 hour delay
        gas_wait = current_leak_rate * (duration_hours / 24)
        lines.append(f"  Isolate in 1 hr:  {gas_now:.3f} MMSCF lost, ${gas_now * GAS_COST_PER_MMSCF:,.0f} gas cost")
        lines.append(f"  Wait {duration_hours:.0f} hrs: {gas_wait:.2f} MMSCF lost, ${gas_wait * GAS_COST_PER_MMSCF:,.0f} gas cost")
        lines.append(f"  Delay cost: ${(gas_wait - gas_now) * GAS_COST_PER_MMSCF:,.0f} additional gas loss")

    return "\n".join(lines)
