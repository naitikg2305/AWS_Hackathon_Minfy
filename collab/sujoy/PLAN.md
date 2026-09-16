# Sujoy — Deploy, UI & Demo

Tools: `generate_incident_report`
Also: Streamlit UI, AgentCore Runtime deployment, demo prep

Drop your architecture notes, plans, and findings here.

## 2026-09-16 19:35 — Phase 1 Complete: Schema, Adapters, Fixtures, UI

### Built:
- `src/app/models/investigation.py` — Pydantic response schema (InvestigationResult + nested models)
- `src/app/adapters/base.py` — Abstract AgentAdapter interface
- `src/app/adapters/mock_agent.py` — Mock adapter returning deterministic fixtures
- `src/app/adapters/agentcore_agent.py` — AgentCore adapter stub (NotImplementedError)
- `src/app/adapters/__init__.py` — Adapter factory (AGENT_MODE=mock|agentcore)
- `src/app/fixtures/confirmed_leak.json` — LK-002 (moderate leak, SEG-05, grounded in real SCADA data)
- `src/app/fixtures/compressor_fp.json` — FP-001 (compressor start at ST-01)
- `src/app/fixtures/temperature_fp.json` — FP-003 (temp/line-pack at ST-02)
- `src/app/streamlit_app.py` — Main Streamlit entry point
- `src/app/components/alarm_queue.py` — Sidebar event selector
- `src/app/components/event_summary.py` — Top-row metrics (classification badge, confidence, severity, location)
- `src/app/components/evidence_panel.py` — Observations, alternatives, integrity risk
- `src/app/components/response_panel.py` — Actions, citations, acknowledge button
- `src/app/components/scada_chart.py` — Plotly SCADA timeline with anomaly onset marker
- `src/tests/test_models.py` — 9 tests for schema validation
- `src/tests/test_mock_adapter.py` — 4 tests for adapter behavior
- `collab/sujoy/PlanSujoy.md` — Full implementation plan

### Test Results:
- 13/13 tests passing
- Streamlit app running on port 3000

### Next:
- Integration with Person 2's agent (swap mock adapter for AgentCore)
- `generate_incident_report` tool
- AgentCore deployment
- Demo polish and evaluation scorecard
