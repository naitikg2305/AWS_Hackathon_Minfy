# Approach Decision & Understanding

## The Real-World Problem

A midstream gas company runs 200 miles of pipeline through 8 SCADA monitoring stations. Every 5 minutes, each station reports pressure, flow rate, temperature, and other readings — 207,000 data points over 90 days.

When gas leaks from a pipeline, two things happen in the data:
- **Pressure drops** between stations
- **Flow imbalance** — more gas goes in one end of a segment than comes out the other (mass balance deficit)

But **three other things look exactly the same:**

1. **Compressor starts** — pressure surge and flow wobble lasting 10-20 minutes
2. **Valve changes** — pressure redistributes across the segment
3. **Cold mornings** — gas contracts overnight, shrinks line pack, moves pressure/flow numbers

Today operators set alarm thresholds. Too sensitive = constant false alarms ($100K+ per unnecessary shutdown, plus alarm fatigue). Too conservative = missed real leaks that cost 6x more to fix. Over 40% of remote pipeline leaks go undetected for over a week.

DOT PHMSA penalties reach $2.7M per violation.

## What's In The Data

Ground truth: **5 confirmed real leaks** and **15 confirmed false positives** across a 90-day window.

Context data: weather, valve positions, compressor status, inspection history (pipe wall thinning), cathodic protection (corrosion protection), third-party encroachment (construction near the line), plus full operating procedures and PHMSA regulations.

The 15 false positives break into 3 clear patterns:
- **Compressor starts** (FP-001,002,005,007,010,013): pressure drop 10-14 PSI, duration 11-20 min, recovers. SCADA compressor_status changes from standby to running.
- **Valve changes** (FP-004,008,011,014): pressure drop 4-17 PSI, duration 17-22 min. SCADA valve_position_pct changes.
- **Temperature/line pack** (FP-003,006,009,012,015): pressure drop 10-18 PSI, duration 9-24 min. Correlates with overnight temp drops in weather data.

The 5 real leaks are different:
- Sustained mass balance deficit (doesn't recover)
- No operational cause (no compressor/valve change, no temp correlation)
- Severity ranges from seep (0.18 mmscfd) to near-rupture (2.4 mmscfd)

---

## Three Approaches Considered

### Approach A: Real-Time Anomaly Triage Agent

**Who it's for:** The SCADA shift operator staring at alarms.

**What it does:** When a pressure anomaly fires, the agent ingests the SCADA readings and automatically cross-references compressor/valve events, weather, line pack physics, and inspection history to classify it as real leak vs. false positive — and explains why with citations.

**Architecture:**
- Detector Tool — scans SCADA data for anomalies (mass balance deficit > threshold, sustained pressure drops)
- Disambiguator Agent — the core intelligence. Pulls corroborating context and applies the operating procedure's decision tree
- Localizer Tool — if classified as a real leak, estimates mile marker from pressure gradients

**Demo flow:** Feed it the 20 labeled events, show it correctly classifying each one with evidence chains.

**Strength:** Tight scope, directly solves the stated problem, easy to demo and validate.
**Risk:** Narrower — might feel like "just a classifier" to judges.

---

### Approach B: Pipeline Integrity Copilot

**Who it's for:** The pipeline integrity engineer doing weekly risk reviews.

**What it does:** Goes beyond alert triage into proactive risk intelligence. Combines leak detection with integrity health scoring — segments with failing cathodic protection + old ILI anomalies + nearby encroachment activity get flagged before a leak happens. Natural language Q&A over all the data.

**Architecture:**
- Risk Scoring Agent — per-segment risk profile combining CP failures, ILI wall-loss depth, encroachment proximity, historical leak patterns
- Anomaly Triage Agent — same as Approach A, enriched with risk context
- Q&A Agent — lets the engineer ask questions over all the data
- Knowledge Base — operating procedures + PHMSA regs indexed for RAG

**Demo flow:** Show the risk dashboard, drill into a high-risk segment, walk through a real leak event where the agent connects CP failure + ILI history + SCADA anomaly.

**Strength:** Richer reasoning depth, uses more of the dataset, shows the agent doing something a human would need hours to do.
**Risk:** Broader scope — more to build, more surface area for things to go wrong.

---

### Approach C: Detect-to-Report Incident Agent

**Who it's for:** The operator + compliance team, end-to-end from detection through regulatory response.

**What it does:** Detects the leak, triages it, recommends isolation valves, estimates gas volume lost, determines if PHMSA reporting is triggered, and pre-fills Form 7100.1 and NRC notification — all grounded in actual regulatory thresholds and operating procedures.

**Architecture:**
- Detection & Triage Agent — anomaly classification (same core as Approach A)
- Response Agent — maps leak location to nearest isolation valves, recommends isolation per operating procedure decision tree
- Compliance Agent — calculates cumulative gas release, checks PHMSA thresholds, generates NRC notification template and pre-fills Form 7100.1
- Evidence Compiler — every recommendation includes specific data rows, procedure sections, and reg citations

**Demo flow:** Walk through LK-002 (moderate, 0.52 MMSCFD on SEG-05). Agent detects it, rules out false positives, recommends closing valves, calculates reporting threshold timeline, generates NRC notification draft with all fields populated from data.

**Strength:** End-to-end story, heavy use of reference docs, practical regulatory value, very differentiated.
**Risk:** Compliance pieces need to be accurate — but the regs are in the reference docs so the agent cites rather than guesses.

---

## Head-to-Head Comparison

| | **A: Anomaly Triage** | **B: Integrity Copilot** | **C: Detect-to-Report** |
|---|---|---|---|
| **Who uses it** | Shift operator during an alarm | Integrity engineer in weekly review | Shift operator + compliance team |
| **Core action** | "Is this a leak? Yes/no + why" | "Which segments are at risk?" + Q&A | "Is this a leak? → isolate → report" |
| **Data files used** | 4-5 (SCADA, weather, valves, labels) | 8-9 (all of them, but shallow) | 8-9 (all of them, deep on each) |
| **Agents/tools** | 1 agent, 3 tools | 3 agents + RAG knowledge base | 1 agent, 6-7 tools |
| **Build time** | ~3-4 hours | ~6-8 hours | ~5-6 hours |
| **Demo impact** | Clean but narrow | Impressive breadth but hard to demo a "moment" | One compelling walkthrough, start to finish |

### Approach A — Anomaly Triage

**Pros:**
- Fastest to build, highest chance of a polished working demo
- Easy to validate — run all 20 labeled events, show accuracy
- Tight scope = fewer things to break

**Cons:**
- Judges might ask "so what happens after you detect it?" and you have no answer
- Uses maybe half the dataset
- Hard to differentiate from other teams doing UC3

### Approach B — Integrity Copilot

**Pros:**
- Most technically impressive on paper
- Uses every file in the dataset
- Risk scoring is genuinely useful and unique

**Cons:**
- Three agents + RAG = most code to write and hardest context management
- Q&A agent is a rabbit hole — open-ended questions are hard to make reliable
- Demo is diffuse — lacks narrative punch
- If any one agent breaks, the whole demo suffers

### Approach C — Detect-to-Report

**Pros:**
- Single narrative arc demos beautifully — one event, five minutes, alarm to regulatory filing
- Uses 8-9 data files deeply (not just touching them, actually reasoning over them)
- Compliance/PHMSA piece is a differentiator nobody else will build
- One agent with tools = simplest architecture, least context risk
- Every output is grounded and citable — exactly what judges score

**Cons:**
- More scope than A — if compliance pieces are wrong, it hurts credibility
- ~2 hours more work than A
- Regulatory accuracy matters — mitigated by citing from reference docs rather than guessing

---

## Decision

**Ranking: C > A > B**

- **C over A** because the extra ~2 hours buys response recommendations + compliance — turns "a classifier" into "a product." Same detection core, just more tools on top.
- **A over B** because B is the riskiest build for a time-boxed hackathon. Multi-agent + RAG + open-ended Q&A is where dry-run teams ran out of time.
- **B's best ideas fold into C cheaply** — when the agent triages a leak on SEG-05, it mentions "this segment also has failing CP and 86% wall-loss from ILI" as context. Risk insight without a whole risk scoring system.

**De-risk strategy:** Start with A's core (detection + disambiguation) and layer C's tools on top incrementally. Always have a working demo; each additional tool just makes it richer.

### Implementation: One Agent, 6-7 Tools

| Tool | What it does | Key data |
|------|-------------|----------|
| `query_scada` | Pressure, flow, mass balance for a station + time window (aggregated) | `scada_timeseries.csv` |
| `check_operational_context` | Compressor start? Valve change? Temp drop? | SCADA + `weather_conditions.csv` + `valve_status.csv` |
| `get_segment_risk_profile` | Known wall loss, failing CP, nearby encroachment | `inspection_history.csv`, `cathodic_protection.csv`, `row_encroachment.csv` |
| `lookup_operating_envelope` | Normal pressure/flow ranges, isolation procedures | `pipeline_operating_procedures.md`, `pipeline_segment_metadata.csv` |
| `locate_leak` | Estimate mile marker from pressure gradients | `scada_timeseries.csv`, `pipeline_segment_metadata.csv` |
| `get_regulatory_guidance` | PHMSA thresholds, NRC notification rules, Form 7100.1 fields | `dot_phmsa_regulatory_reference.md` |
| `generate_incident_report` | Pre-fill Form 7100.1 from event data | All of the above |
