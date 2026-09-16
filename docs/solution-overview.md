# Pipeline Leak Detection: Detect-to-Report Incident Agent

## The Problem

A gas pipeline operator has 8 monitoring stations across 200 miles of pipeline. When pressure drops or flow changes, it could mean a real leak — or it could be a compressor starting up, a valve moving, or a cold night shrinking the gas. Today, operators can't tell the difference fast enough. Set alarms too tight and you get constant false alerts ($100K+ per unnecessary shutdown). Set them too loose and real leaks go undetected for days, with repair costs jumping 600% and federal penalties up to $2.7M per violation.

The core challenge: **knowing whether an anomaly is a real leak or just normal pipeline behavior — and if it is real, what to do about it, fast.**

## Our Solution

An AI agent that handles the full incident lifecycle — from the moment an anomaly appears to the regulatory report that follows.

### What it does, step by step

**1. Detects and classifies the anomaly**
The agent scans SCADA readings and checks: was there a compressor start? A valve change? A big temperature drop overnight? If the anomaly matches a known false-positive pattern, it says so and explains why. If it doesn't match any known pattern and the mass balance deficit persists, it flags it as a real leak.

**2. Recommends a response**
For confirmed leaks, the agent looks up which pipeline segment is affected, finds the nearest isolation valves, and recommends actions based on leak severity:
- Small leak (< 0.3 MMSCFD): reduce pressure, send a crew
- Moderate leak (> 0.3 MMSCFD): close the isolation valves
- Near-rupture (> 50 psi drop in < 5 min): emergency shutdown

**3. Handles compliance**
The agent calculates how much gas has been or will be lost, checks that number against federal reporting thresholds (3 million cubic feet triggers a mandatory report), and pre-fills the required NRC notification and PHMSA Form 7100.1 — pulling every number from the actual data.

### Every claim is grounded in evidence

Nothing is made up. Every conclusion the agent states traces back to a specific data row, operating procedure section, or regulation. If the data doesn't support a conclusion, the agent says so.

**Example — Event LK-002 (moderate leak on Segment 5):**
- Detection: "Mass balance deficit of 0.52 MMSCFD sustained for >10 minutes at ST-05. No compressor start logged. No valve change. Temperature stable. Classified as real leak per Operating Procedures Section 3.1."
- Response: "Leak at mile 119.3 on SEG-05. Nearest isolation valves: V-112 (mile 112) and V-122 (mile 122). Leak rate > 0.3 MMSCFD — recommend isolating segment per Operating Procedures Section 3.2."
- Compliance: "At 0.52 MMSCFD, cumulative release reaches the 3 MMSCF reporting threshold in ~5.8 days. NRC notification required within 1 hour per 49 CFR 191.5. Draft NRC notification and Form 7100.1 generated."

## Architecture

Three agents, each with a clear job:

| Agent | What it does | Key data sources |
|---|---|---|
| Detection & Triage | Scans for anomalies, cross-references operational context, classifies as leak or false positive | SCADA readings, valve status, weather, compressor logs |
| Response | Maps leak location to nearest valves, recommends isolation actions based on severity | Segment metadata, operating procedures |
| Compliance | Calculates gas loss, checks reporting thresholds, generates regulatory filings | PHMSA regulations, NRC notification template |

Built with the Strands Agents SDK, deployed on Amazon Bedrock AgentCore, with a Streamlit interface for the demo.

## Why This Approach

- **Solves the real problem**: operators need to know if it's real, what to do, and what to report — not just a classification score
- **Every answer shows its work**: data rows, procedure sections, and regulation citations attached to every recommendation
- **Practical value**: cuts incident response from hours of manual cross-referencing to minutes of agent-assisted workflow
