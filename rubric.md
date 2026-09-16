# Judging Rubric — Pipeline Leak Detection & Integrity Agent

## 1. Agentic Behavior (Is the solution actually agentic? Does it call tools and perform actions?)

**Status: PASS**

- **Strands Agent** with 6 `@tool`-decorated functions — model autonomously decides which tools to call
- System prompt defines a 3-phase workflow (Detect & Triage, Response, Compliance) but the agent skips phases when not needed (e.g. false positives skip isolation/reporting)
- Real-time SSE streaming via `agent.stream_async()` — not batch request/response
- Tool chain observed in live invocations:
  - `query_scada` — pulls SCADA readings for a station/time window, returns aggregated pressure/flow/MBD stats
  - `check_operational_context` — checks for compressor starts, valve changes, temperature drops that explain the anomaly
  - `locate_leak` — estimates leak location via pressure gradient ratio between bounding stations
  - `get_segment_risk_profile` — reads ILI inspection, cathodic protection, encroachment data
  - `lookup_operating_envelope` — computes normal ranges from SCADA baseline (5th-95th percentile)
  - `get_regulatory_guidance` — evaluates PHMSA reporting thresholds (49 CFR 191)
- Agent reasons over tool outputs to classify events, not just forwarding results

**Key files:**
- Agent entry point: `agentcore-deploy/pipelineleakagent/app/pipeline_leak_agent/main.py`
- All tools: `src/tools/` (9 tool files)

---

## 2. Source Code Integrity (No shortcuts or faked data)

**Status: PASS**

- All 9 tools compute from real CSV data (207K-row SCADA timeseries + 6 supporting datasets)
- Zero hardcoded responses — no event-ID matching, no pre-written verdicts
- Only hardcoded values are domain constants with cited sources:
  - PHMSA thresholds from 49 CFR 191.3/191.5 (federal regulation)
  - Henry Hub gas price $3.50/MCF (market reference, used with gas_composition.csv heating values)
  - Shutdown cost $100K, max penalty $2.7M (from operating procedures)
  - Transient signatures (compressor start, valve change, temperature line pack) from operating procedures document
- Operating envelope pressure/flow ranges computed dynamically from SCADA baseline data (5th-95th percentile) — not static lookup tables
- Confidence scoring reads 4 CSVs (SCADA, weather, cathodic protection, inspection history) and checks system-wide deficit across all stations
- Mock adapter (`mock_agent.py`) is clearly labeled, only activates when `AGENT_MODE=mock` — never in production path

**Data files used:**
| File | Rows | Purpose |
|------|------|---------|
| `scada_timeseries.csv` | 207,360 | 8 stations, 90 days, 15-min intervals |
| `pipeline_segment_metadata.csv` | 7 | Segment geometry, MAOP, valve locations |
| `inspection_history.csv` | varies | ILI findings, wall loss % |
| `cathodic_protection.csv` | varies | CP readings, pass/fail |
| `row_encroachment.csv` | varies | Right-of-way encroachment activity |
| `gas_composition.csv` | varies | Heating values for cost calculation |
| `weather_data.csv` | varies | Temperature, wind, precipitation |
| `valve_status.csv` | varies | Valve positions and changes |

---

## 3. Video / UI / UX

**Status: READY**

- **5 tabs**: Analysis & Response, Confidence Scoring, What-If Scenarios, SCADA Timeline, Evaluation Scorecard
- Sidebar alarm queue shows all 20 labeled events (5 leaks, 15 false positives) with color-coded badges
- Pipeline schematic map reads station/segment layout from CSV, highlights affected segment, shows estimated leak location with uncertainty band
- SCADA timeline chart (Plotly, 3 subplots: pressure, flow, MBD) with anomaly onset marker
- What-If scenario panel (continue/double/escalate/isolate) with cost projections and PHMSA threshold timelines
- Confidence panel explicitly states "Confidence derived from 4 measurable signals — not LLM-estimated"
- "DECISION SUPPORT ONLY" disclaimer on response panel
- Dark theme compatible — no hardcoded white backgrounds, transparent chart backgrounds, opacity-based muted text
- Agent mode indicator in sidebar (Mock/Live/AgentCore)

**Key files:**
- Main app: `src/app/streamlit_app.py`
- Components: `src/app/components/` (7 component files)

---

## 4. AgentCore Usage

**Status: FULLY DEPLOYED**

- **Runtime ARN**: `arn:aws:bedrock-agentcore:us-east-1:260287467863:runtime/pipelineleakagent_pipeline_leak_agent-9djKrBCyoX`
- **Runtime Status**: READY
- **Build**: CodeZip (bundled Python app + 21MB data files)
- **Runtime**: PYTHON_3_14
- **Protocol**: HTTP with SSE streaming
- **Network**: PUBLIC
- **Model**: Bedrock Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)

**How the UI calls AgentCore:**
- `src/app/adapters/agentcore_agent.py` uses `boto3.client("bedrock-agentcore").invoke_agent_runtime()`
- Sends natural language prompt to deployed runtime
- Parses SSE response stream (`contentBlockDelta` text deltas)
- Extracts structured fields (classification, severity, location, observations) via regex from agent's natural language response
- `AGENT_MODE` environment variable switches between mock/live/agentcore adapters

**AgentCore features used:**
- CodeZip deployment with bundled data
- HTTP protocol with SSE streaming
- Public network access
- Session management (conversation continuity via session IDs)
- CloudFormation-based infrastructure (CDK stack)

---

## Architecture Summary

```
Operator (Streamlit UI on EC2:3000)
    |
    | AGENT_MODE=agentcore
    v
boto3 invoke_agent_runtime() --> AgentCore Runtime (Bedrock)
                                      |
                                      v
                                 Strands Agent (Claude Sonnet 4.5)
                                      |
                                      | autonomously calls tools
                                      v
                              +-------------------+
                              | query_scada       |
                              | check_op_context  |
                              | locate_leak       | --> all read from
                              | get_risk_profile  |     bundled CSV data
                              | lookup_envelope   |
                              | get_reg_guidance  |
                              +-------------------+
                                      |
                                      v
                              Grounded verdict with citations
                              (streamed back via SSE)
```

## Team

| Person | Role | Key Contributions |
|--------|------|-------------------|
| Naitik | Data & Detection Logic | SCADA query, operational context, leak localization, confidence scoring tools |
| Sriram | Agent Architecture | Strands agent, system prompt, risk profile, operating envelope, regulatory guidance tools |
| Sujoy | Deploy / UI / Demo | Streamlit UI, AgentCore deployment, adapter layer |
