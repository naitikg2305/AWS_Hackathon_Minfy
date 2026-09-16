# PlanSujoy — Person 3: Deploy, UI & Demo

## Context

Sujoy owns the **operator experience, integration, deployment, and demo** for the Pipeline Leak Detection & Integrity Agent hackathon project. The team chose Approach C (Detect-to-Report), with one agent and 6-7 tools.

**Current state:** Zero application code exists. `src/` has empty `__init__.py` stubs. No UI, no adapters, no models, no fixtures. All data files and reference docs are in place. Naitik (Person 1) and Sriram (Person 2) have not started coding yet either.

**Strategy:** Build a polished mock-driven operator UI with a frozen response contract first. Person 2 connects the real agent later via adapter swap.

---

## Phase 1: Schema + Adapters + Mock Fixtures (do first)

### 1.1 Create Pydantic response models
- **File:** `src/app/models/investigation.py`
- Define `InvestigationResult` as the top-level Pydantic model matching the agreed JSON contract
- Nested models: `EstimatedLocation`, `Observation`, `AlternativeConsidered`, `IntegrityContext`, `RecommendedAction`, `Citation`
- Classification enum: `LIKELY_LEAK`, `FALSE_POSITIVE`, `INCONCLUSIVE`
- Severity enum: `seep`, `moderate`, `significant`, `near_rupture`
- Status enum: `completed`, `in_progress`, `error`, `timeout`

### 1.2 Create the adapter interface
- **File:** `src/app/adapters/base.py`
- Abstract base class `AgentAdapter` with method: `investigate_event(event_id, station_id, start_timestamp, end_timestamp) -> InvestigationResult`
- Also define error/timeout return types

### 1.3 Create mock adapter
- **File:** `src/app/adapters/mock_agent.py`
- Implements `AgentAdapter`, returns deterministic responses from fixture files
- Routes by event_id to the correct fixture; returns "unknown event" for unrecognized IDs

### 1.4 Stub AgentCore adapter
- **File:** `src/app/adapters/agentcore_agent.py`
- Implements `AgentAdapter`, raises `NotImplementedError("AgentCore not configured — set AGENT_MODE=agentcore and provide AGENTCORE_RUNTIME_ARN")`
- Placeholder for Person 2 integration

### 1.5 Create 3 demo fixtures (grounded in real data)
- **File:** `src/app/fixtures/confirmed_leak.json` — based on **LK-002** (moderate leak, SEG-05, mile 119.3, 0.52 mmscfd, onset 2026-01-04T23:55)
- **File:** `src/app/fixtures/compressor_fp.json` — based on **FP-001** (compressor start at ST-01, 13.8 psi drop, 19 min, 2025-12-04T14:00)
- **File:** `src/app/fixtures/temperature_fp.json` — based on **FP-003** (temp/line-pack at ST-02, 17.5 psi drop, 11 min, 2025-12-11T05:00)
- Each fixture must follow the `InvestigationResult` schema exactly, with real citations to actual CSV rows and reference doc sections

### 1.6 Adapter factory
- **File:** `src/app/adapters/__init__.py`
- `get_adapter(mode: str) -> AgentAdapter` — reads `AGENT_MODE` env var (default `mock`), returns MockAgentAdapter or AgentCoreAdapter

---

## Phase 2: Streamlit Operator Console UI

### 2.1 Main app entry point
- **File:** `src/app/streamlit_app.py`
- Page config: wide layout, "Pipeline Leak Detection Agent" title
- Sidebar: event selector (dropdown of demo events + manual entry), adapter mode display
- Main area: renders the 5 sections below

### 2.2 UI Components

**File:** `src/app/components/alarm_queue.py`
- List of available events (from fixtures + labeled events CSVs)
- Click to investigate; shows event_id, station, timestamp
- Color-coded status indicators

**File:** `src/app/components/event_summary.py` — Top row
- Event ID, Classification badge (red=LIKELY_LEAK, green=FALSE_POSITIVE, yellow=INCONCLUSIVE)
- Confidence gauge, Severity badge, Segment + mile marker with uncertainty
- Summary text

**File:** `src/app/components/evidence_panel.py` — Center area
- Left column: SCADA timeline chart (pressure, flow, mass-balance) using Streamlit's native charting or plotly
  - Pull actual SCADA data from `data/scada_timeseries.csv` for the affected station/timewindow
  - Vertical marker at anomaly onset
- Right column: "Why this classification" section, alternatives considered (expandable), integrity risk indicators (ILI, CP, encroachment)

**File:** `src/app/components/response_panel.py` — Bottom area
- Recommended actions (priority-ordered)
- Expandable citations panel (source, locator, claim)
- Trace ID display
- "Acknowledge" button (visual only for demo)
- For false positives: green styling, "No emergency response recommended", continued monitoring note

### 2.3 State handling
- Use `st.session_state` for current event, investigation result, loading state
- Show spinner during "investigation" (mock has artificial 1-2s delay for realism)
- Handle error, timeout, and insufficient-evidence states with appropriate UI

### 2.4 SCADA chart helper
- **File:** `src/app/components/scada_chart.py`
- Loads a time window of SCADA data for the relevant station(s)
- Plots pressure_psi, flow_mmscfd, mass_balance_deficit_mmscfd over time
- Highlights the anomaly onset window
- Uses pandas for data loading (read only the needed rows, not all 207K)

---

## Phase 3: Tests

- **File:** `src/tests/test_models.py`
  - Validate all 3 fixtures parse into `InvestigationResult` without errors
  - Test enum validation (invalid classification/severity rejected)
  - Test required fields are enforced

- **File:** `src/tests/test_mock_adapter.py`
  - Mock adapter returns correct fixture for each demo event_id
  - Mock adapter returns error response for unknown event_id
  - Response conforms to Pydantic schema

---

## Phase 4: Integration with Person 2's Agent

- Replace `AgentCoreAdapter` stub with real implementation
- Adapter calls Person 2's `investigate_event()` function or AgentCore runtime endpoint
- Test all states: real leak, false positive, insufficient evidence, timeout, invalid response, missing citation
- Validate response against Pydantic schema; graceful degradation if fields are missing

---

## Phase 5: AgentCore Deployment

```bash
agentcore dev                              # local test
agentcore dev "Investigate event LK-002"   # test with real input
agentcore deploy --dry-run                 # validate
agentcore deploy                           # deploy
agentcore invoke "Investigate event LK-002" # production test
agentcore logs                             # check logs
agentcore traces list                      # inspect traces
```

---

## Phase 6: Demo Polish

- Pre-select LK-002 as the default demo event
- Ensure smooth transitions between leak and false-positive views
- Evaluation scorecard: run all 20 labeled events, report accuracy, FP reduction, citation completeness, avg investigation time
- Live demo script: (1) LK-002 real leak in depth, (2) FP-001 compressor FP, (3) optionally FP-003 temperature FP

---

## Folder Structure (final)

```
src/
  app/
    streamlit_app.py
    components/
      __init__.py
      alarm_queue.py
      event_summary.py
      evidence_panel.py
      response_panel.py
      scada_chart.py
    adapters/
      __init__.py
      base.py
      mock_agent.py
      agentcore_agent.py
    models/
      __init__.py
      investigation.py
    fixtures/
      confirmed_leak.json
      compressor_fp.json
      temperature_fp.json
  tests/
    __init__.py
    test_models.py
    test_mock_adapter.py
```

---

## Sync Points with Person 2

**Before Person 2 finishes — give them:**
- Final JSON response contract (InvestigationResult schema)
- Adapter function signature
- Three mock responses as examples
- Required error behavior
- Expected citation format

**When agent is ready — get from them:**
- Local invocation method
- Streaming or non-streaming response
- Runtime input payload format
- Agent timeout expectation
- AgentCore runtime name and AWS Region

---

## Verification

1. **Schema:** `pytest src/tests/test_models.py` — all fixtures validate
2. **Adapter:** `pytest src/tests/test_mock_adapter.py` — mock routing works
3. **UI:** `streamlit run src/app/streamlit_app.py --server.port 3000` — visually verify:
   - LK-002 shows red classification, evidence chain, recommended actions, citations
   - FP-001 shows green classification, compressor start explanation, no emergency action
   - FP-003 shows green classification, temperature explanation
   - Loading spinner appears during investigation
   - Unknown event shows error state
4. **Charts:** SCADA timeline renders correctly with anomaly onset marker

---

## Immediate Next Action

Start with Phase 1 (schema + adapters + fixtures), then Phase 2 (UI). This gives a working demo against mocks in ~2-3 hours, independent of Person 1 and Person 2's progress.
