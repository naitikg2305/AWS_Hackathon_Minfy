# Team Sync Log

All team members: append your updates here after every push so everyone sees the full picture.

---

## 2026-09-16 — Sujoy: Created comprehensive post-hackathon submission document

### What changed
- Created `presentation.md` — full narrative submission document (not slides format)
- 12 sections + 3 appendices covering architecture, agent reasoning, tool design, evaluation, deployment, and known limitations
- Includes verification checklist: every claim traced to source code lines and data files
- Pulled Sriram's latest changes (ground truth leakage removal) and verified 20/20 accuracy still holds

### For Sriram
Your code review changes (removing ground truth leakage from query_scada, live_agent, compute_confidence, etc.) are documented in the presentation as a key design strength.

### For Naitik
AgentCore deployment status and ARN are documented with honest notes about the confidence parsing limitation.

---

## 2026-09-16 — Sujoy: Completed comprehensive UI audit

### What changed
- `collab/sujoy/review.md` — 333-line audit across 9 evaluation dimensions with 19 prioritized findings
- `collab/sujoy/screenshots/` — Automated Playwright screenshots at two demo resolutions
- Key P0 findings: severity mismatch for escalating events, alarm queue uses ground truth labels

---

## 2026-09-16 — Naitik: Agent deployed to AgentCore Runtime + adapter wired

### What changed
- Deployed full agent to **AgentCore Runtime** (CodeZip, HTTP protocol, us-east-1)
- Runtime ARN: `arn:aws:bedrock-agentcore:us-east-1:260287467863:runtime/pipelineleakagent_pipeline_leak_agent-9djKrBCyoX`
- Status: **READY** — tested with FP-001, correctly classifies false positives
- Wired `AgentCoreAdapter` in `src/app/adapters/agentcore_agent.py` — calls deployed agent via boto3, parses SSE response into structured `InvestigationResult`
- Deployment package at `agentcore-deploy/pipelineleakagent/` with all 6 tools + data files
- Model: Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)

### For Sujoy (UI)
To use the deployed agent from the UI, set `AGENT_MODE=agentcore`:
```bash
AGENT_MODE=agentcore streamlit run src/app/streamlit_app.py --server.port 3000
```
The adapter handles the full invocation + response parsing automatically.

### For Sriram
All 6 tools (yours + mine) are deployed and working in AgentCore. The system prompt enforces the 3-phase workflow.

---

## 2026-09-16 — Sujoy: Integrated Sriram's confidence scoring & what-if scenarios into UI

### What changed
- New `src/app/components/confidence_panel.py` — calls `compute_confidence` tool, renders visual breakdown with progress bars for each of 4 weighted signals
- New `src/app/components/scenario_panel.py` — calls `simulate_scenario` tool with 4 scenarios (continue/double/escalate/isolate), renders comparison cards with cost estimates and PHMSA triggers
- Updated `src/app/streamlit_app.py` — added "Confidence Scoring" and "What-If Scenarios" tabs (scenarios only shown for leak events)

### For Sriram
Your `compute_confidence` and `simulate_scenario` tools are now fully integrated into the Streamlit UI. The confidence panel parses your text output into visual progress bars. The scenario panel lets operators adjust duration and escalation rate with sliders.

### For Naitik
No changes to tools or adapters. All 89 tests still pass.

---

## 2026-09-16 — Naitik: Fixed integration issues, agent runs end-to-end

### What changed
- Added `@tool` decorator to all 3 of my tools (Strands requires it)
- Fixed model ID: `us.anthropic.claude-sonnet-4-20250514-v1:0` is LEGACY/unavailable. Changed to `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Sonnet 4.5, ACTIVE)
- Tested full agent pipeline: FP-001 correctly classified as FALSE POSITIVE with evidence chains and citations

### For Sriram
Your code integrated cleanly. One fix: the model ID had to change — Sonnet 4 is LEGACY in this lab account. Sonnet 4.5 works.

### For Sujoy
Agent is working end-to-end. You can run `python3 -m src.main FP-001` to test.

---

## 2026-09-16 — Naitik: Full validation — 20/20 events pass (100%)

### What changed
- Improved `check_operational_context.py`: wider lookback windows (6h for compressor/valve, 12h for weather), better temp threshold (>15F)
- Added `validate_all_events.py`: automated test harness for all 20 labeled events
- Detection logic: **sustained mass balance deficit is the primary signal** — operational context helps explain FPs but doesn't override MBD for real leaks

### Validation Results
```
Leaks detected:         5/5  (100%)
FPs correctly rejected: 15/15 (100%)
Avg localization error: 5.0 miles
FP cause type match:    8/15 (compressor starts have no explicit SCADA flag — fall back to temp)
```

| Leak | Severity | True Mile | Est. Mile | Error |
|------|----------|-----------|-----------|-------|
| LK-001 | seep | 47.2 | 37.5 | 9.7 mi |
| LK-002 | moderate | 119.3 | 118.5 | 0.8 mi |
| LK-003 | significant | 72.0 | 64.1 | 7.9 mi |
| LK-004 | moderate | 182.1 | 177.5 | 4.6 mi |
| LK-005 | near_rupture | 13.6 | 15.7 | 2.1 mi |

### For Sriram (Agent)
Tools are ready — unchanged signatures:
```python
query_scada(station_id: str, start_time: str, end_time: str) -> dict
check_operational_context(station_id: str, event_time: str) -> dict
locate_leak(station_id: str, event_time: str) -> dict
```
Run `python3 src/tools/validate_all_events.py` from `src/tools/` to verify everything works.

### For Sujoy (UI/Deploy)
Tools are in `src/tools/`. Each has a `__main__` block for standalone testing.
The validation script is also a good reference for how to call the tools.

---

## 2026-09-16 — Naitik: Built all 3 Person 1 tools (initial)

- `src/tools/query_scada.py` — aggregated SCADA summary for station + time window
- `src/tools/check_operational_context.py` — compressor/valve/temp false positive detection
- `src/tools/locate_leak.py` — pressure gradient localization with valve mapping
