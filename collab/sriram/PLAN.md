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
