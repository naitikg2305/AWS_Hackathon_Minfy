# Sriram — Agent Architecture & Orchestration

Tools: `get_segment_risk_profile`, `lookup_operating_envelope`, `get_regulatory_guidance`
Also: Strands agent + system prompt, wiring all tools together

## 2026-09-16 — Built full agent pipeline (detect → respond → comply)

### What I built
- **3 tools (mine)**:
  - `src/tools/get_segment_risk_profile.py` — pulls segment metadata, inspection history, CP failure rate, active encroachments from CSVs
  - `src/tools/lookup_operating_envelope.py` — returns normal pressure/flow ranges, false-positive transient signatures, isolation decision tree
  - `src/tools/get_regulatory_guidance.py` — calculates cumulative gas loss, checks PHMSA thresholds (3 MMSCF, $50K), returns reporting requirements with citations

- **3 tools (Naitik's — working implementations so agent runs end-to-end)**:
  - `src/tools/query_scada.py` — queries SCADA CSV for a station/time window, returns summary stats
  - `src/tools/check_operational_context.py` — checks for compressor starts, valve changes, temp drops in ±2hr window
  - `src/tools/locate_leak.py` — estimates leak mile marker from pressure gradients, identifies nearest isolation valves

- **Agent** (`src/agents/pipeline_agent.py`):
  - Strands Agent with Bedrock Claude Sonnet 4
  - System prompt enforces 3-phase workflow: Detection & Triage → Response → Compliance
  - All 6 tools wired in
  - Output format: Classification, Evidence Chain, Response Recommendation, Compliance Status, Draft NRC Notification

- **Entry point** (`src/main.py`):
  - `python -m src.main LK-002` for single event analysis
  - `python -m src.main` for interactive mode
  - Pre-built prompts for all 5 leaks (LK-001 to LK-005) and 2 FP examples

### Tested
- LK-002 (moderate leak, SEG-05): correctly classified as leak, recommended V-112/V-122 isolation, calculated 5.8 days to PHMSA threshold, generated NRC notification draft
- FP-001 (compressor start, ST-01): correctly classified as false positive, no response/compliance needed

### Next
- Naitik: improve tool implementations if needed (query_scada, check_operational_context, locate_leak are working but basic)
- Sujoy: build Streamlit UI that calls the agent, AgentCore deployment
- Me: refine system prompt based on testing more events, add generate_incident_report tool for Sujoy

## 2026-09-16 — Added confidence scoring, what-if scenarios, batch scorecard

### What I built
- **`src/tools/compute_confidence.py`** — data-driven confidence scoring (not LLM-guessed)
  - 4 weighted signals: FP checks clear (35%), deficit persistence (25%), leak rate severity (25%), segment integrity risk (15%)
  - Returns score like "72% HIGH" with full breakdown showing which signals contributed

- **`src/tools/simulate_scenario.py`** — what-if scenario projections
  - Supports: continue, double, escalate, isolate scenarios
  - Calculates: cumulative gas loss, time to PHMSA threshold, cost estimates (gas + shutdown + penalty exposure)
  - Shows comparison: "isolate now vs. wait X hours" with dollar cost of delay

- **`src/batch_scorecard.py`** — runs all 20 events through tool-based classification
  - 5 real leaks + 15 false positives vs. ground truth
  - Result: **20/20 (100% accuracy)**, avg confidence 81%
  - Run with `python -m src.batch_scorecard`

- **Updated agent** — system prompt now includes confidence scoring and what-if phases, 8 tools wired

### Tested
- Batch scorecard: 20/20 correct (5/5 leaks detected, 15/15 FPs rejected)
- LK-002 full agent: confidence 72% HIGH, what-if shows $103K cost if delayed 48hrs, PHMSA damage threshold exceeded
- LK-005 full agent: near-rupture correctly triggers ESD + immediate NRC notification
- FP-001 full agent: correctly classified as false positive, no action needed

## 2026-09-16 — Code review: removed all ground truth leakage and hardcoded values

### Issues found and fixed
1. **`query_scada.py`** — was exposing `event_flag` ground truth labels (`leak`, `false_positive`) to the agent. Replaced with `operational_events` that only surfaces `compressor_start` and `valve_change` (legitimate operational logs).
2. **`live_agent.py`** — classification depended on `has_leak_flag` from ground truth. Now classifies purely from `mbd_sustained and not has_operational_cause`.
3. **`lookup_operating_envelope.py`** — pressure/flow ranges were hardcoded. Rewrote to compute 5th-95th percentile envelopes from SCADA baseline data, read MAOP from `pipeline_segment_metadata.csv`.
4. **`simulate_scenario.py`** — gas cost was hardcoded. Now derived from `gas_composition.csv` heating values × Henry Hub price. All other constants have source citations.
5. **`compute_confidence.py`** — 4th FP check read from `labeled_false_positive_events.csv` (ground truth). Replaced with system-wide deficit analysis (checks if deficit is localized vs. all stations).
6. **`batch_scorecard.py`** — `classify_event()` used `leak_flags` count from `event_flag` column. Removed entirely; classification now uses sustained deficit + operational cause only.

### Verified
- Batch scorecard: still 20/20 (100%) after all fixes
- Full agent test (LK-002): all 8 tools fire correctly, analysis is entirely data-driven
