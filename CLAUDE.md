# Pipeline Leak Detection & Integrity Agent (UC3)

## What This Is
Hackathon project — Approach C: Detect-to-Report Incident Agent. An AI that handles the full incident lifecycle: detect anomaly → classify as real leak or false positive → recommend isolation response → generate PHMSA regulatory filing. Built with Strands Agents SDK, deployed on Amazon Bedrock AgentCore, with a Streamlit demo UI.

See `docs/approach-decision-and-understanding.md` for the full rationale.
See `docs/solution-overview.md` for the judge-facing summary.

## Architecture — How the Pieces Fit

One Strands agent with 7 tools. The agent receives a natural language question from the operator (via Streamlit UI), calls the tools in sequence, and returns a grounded verdict with citations.

```
┌──────────────────────────────────────────────────────────────┐
│                    Streamlit UI (Sujoy)                       │
│  Operator types: "Pressure drop at ST-03 around midnight     │
│  on Jan 27 — is this a leak?"                                │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│              Strands Agent (Sriram)                           │
│  System prompt enforces: cite every claim, fail loud,        │
│  follow PHMSA rules. Model: Bedrock Claude.                  │
│                                                              │
│  Calls these tools in order:                                 │
│  1. query_scada         ─── Naitik (DONE)                    │
│  2. check_operational_context ─── Naitik (DONE)              │
│  3. locate_leak         ─── Naitik (DONE)                    │
│  4. get_segment_risk_profile ─── Sriram                      │
│  5. lookup_operating_envelope ─── Sriram                     │
│  6. get_regulatory_guidance ─── Sriram                       │
│  7. generate_incident_report ─── Sujoy                       │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│              AgentCore Runtime (Sujoy)                        │
│  Deployed via `agentcore dev --port 3000`                    │
│  (port 8080 is VS Code — never use it)                       │
└──────────────────────────────────────────────────────────────┘
```

## Tool Interfaces — EVERY TOOL MUST MATCH THESE SIGNATURES

Naitik's tools are DONE and in `src/tools/`. Sriram and Sujoy: import and use them as-is. Build your tools to match the same pattern (function that takes simple args, returns a dict, <150 words output).

### Naitik's tools (DONE — src/tools/)

```python
# src/tools/query_scada.py
query_scada(station_id: str, start_time: str, end_time: str) -> dict
# Returns: pressure stats, flow, mass_balance_deficit (with sustained flag),
#          compressor_status, valve_position, event_flags
# Example: query_scada("ST-03", "2026-01-27T23:30:00", "2026-01-28T00:30:00")

# src/tools/check_operational_context.py
check_operational_context(station_id: str, event_time: str) -> dict
# Returns: has_operational_cause (bool), likely_false_positive (bool),
#          explanations[] with type (compressor_start/valve_change/temperature_line_pack)
# Example: check_operational_context("ST-03", "2026-01-28T00:00:00")

# src/tools/locate_leak.py
locate_leak(station_id: str, event_time: str) -> dict
# Returns: segment_id, estimated_mile_marker, nearest_valves, recommended_isolation
# Example: locate_leak("ST-03", "2026-01-28T00:00:00")
```

### Sriram's tools (TO BUILD — src/tools/)

```python
# src/tools/get_segment_risk_profile.py
get_segment_risk_profile(segment_id: str) -> dict
# Should return: ILI inspection findings (wall loss %), CP status (failing?),
#                encroachment activity, overall risk assessment
# Data: inspection_history.csv, cathodic_protection.csv, row_encroachment.csv

# src/tools/lookup_operating_envelope.py
lookup_operating_envelope(station_id: str) -> dict
# Should return: normal pressure range, normal flow range, isolation procedures,
#                response decision tree (seep/moderate/significant/near_rupture)
# Data: pipeline_operating_procedures.md, pipeline_segment_metadata.csv

# src/tools/get_regulatory_guidance.py
get_regulatory_guidance(leak_rate_mmscfd: float, estimated_volume_mcf: float) -> dict
# Should return: is PHMSA reporting required, NRC notification deadline,
#                Form 7100.1 required fields, relevant reg citations
# Data: dot_phmsa_regulatory_reference.md
```

### Sujoy's tools (TO BUILD — src/tools/)

```python
# src/tools/generate_incident_report.py
generate_incident_report(event_data: dict) -> dict
# Should return: pre-filled Form 7100.1 fields, NRC notification draft,
#                timeline of events with citations
# Data: aggregates output from all other tools
```

## Sriram — Agent Build Instructions

1. `pip install strands-agents strands-agents-tools boto3`
2. Check which Bedrock model IDs are enabled: `aws bedrock list-foundation-models --query "modelSummaries[?contains(modelId,'claude')]" --output table`
3. Build the agent in `src/agents/pipeline_agent.py`
4. Import Naitik's tools from `src/tools/` and wrap them as Strands tools
5. System prompt MUST enforce:
   - Cite specific file + row for every claim
   - Say "data doesn't support this" when evidence is insufficient
   - Follow PHMSA 5-minute notification rule for significant+ leaks
   - Cap tool output summaries in the response
6. Test against all 20 labeled events (5 leaks in `data/labeled_leak_events.csv`, 15 FPs in `data/labeled_false_positive_events.csv`)

## Sujoy — UI & Deploy Instructions

1. Build Streamlit app in `ui/app.py` — run on port 3000 (NEVER 8080)
2. Input: text box for operator question + optional station/time selectors
3. Output: agent response with expandable sections for evidence, citations, and incident report
4. The agent returns structured dicts from each tool — render them as cards/tables
5. For AgentCore deployment: `agentcore dev --port 3000` for local, then deploy to Runtime
6. Demo scenarios to prep:
   - LK-003: significant leak on SEG-03 (good localization story)
   - FP-001: compressor start false positive (disambiguation)
   - LK-005: near-rupture on SEG-01 (emergency response + PHMSA reporting)

## Key Gotchas (ALL TEAM MEMBERS READ THIS)
- `valve_status.csv` segment_id is bare "01" — Naitik's tools already normalize this. If you read valve_status directly, add `"SEG-" + segment_id.zfill(2)`.
- Don't paste 207K-row SCADA file into agent context. All tools return aggregated summaries.
- Cap every tool return to <150 words structured output.
- Port 8080 is VS Code. Use 3000+ for dev servers.
- Check Bedrock model IDs before hardcoding — models vary by lab account.

## Git Sync Rule (ALWAYS FOLLOW THIS — MANDATORY FOR EVERY CLAUDE SESSION)

**Ask the user which person they are (Naitik, Sriram, or Sujoy) at the start of every new session.**

**Before every task:** run `git pull` and read `collab/SYNC.md` to see what changed.

**After every task — ALL of these, every time, no exceptions:**

```
1. git pull (get latest from teammates)
2. Do the work
3. Update collab/<your-name>/PLAN.md with what you did (append, don't overwrite)
4. Update collab/SYNC.md with a short entry so the whole team sees it
5. Update THIS FILE (CLAUDE.md) if you:
   - Changed a tool signature or added a new tool
   - Changed the project structure (new files/folders)
   - Moved a tool from "TO BUILD" to "DONE" in the tool interfaces section above
   - Changed how the agent works, the UI design, or the deploy setup
   - Found a new gotcha that other team members need to know
6. git add -A
7. git commit with a clear message
8. git push (if push fails due to conflict: git pull --rebase then push again)
```

**CLAUDE.md is the single source of truth.** If you built a tool, mark it DONE here. If you changed a signature, update it here. If you found a bug, add it to gotchas. The other Claudes read this file at the start of every session — if it's not in CLAUDE.md, they don't know about it.

Folders: collab/naitik/, collab/sriram/, collab/sujoy/

## Commands
```bash
pip install -r requirements.txt
streamlit run ui/app.py --server.port 3000
agentcore dev --port 3001
python3 src/tools/query_scada.py          # test Naitik's tools standalone
python3 src/tools/check_operational_context.py
python3 src/tools/locate_leak.py
```
