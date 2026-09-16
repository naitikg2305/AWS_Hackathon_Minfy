# Pipeline Leak Detection & Integrity Agent (UC3)

## What This Is
Hackathon project: an agentic AI that analyzes SCADA pipeline data, distinguishes real leaks from false positives (compressor starts, valve changes, temperature shifts), and grounds every claim in specific data rows.

## Project Structure
```
/workshop
├── data/                    # CSV datasets + reference docs (not in git, download locally)
│   ├── scada_timeseries.csv        # 207K rows, 8 stations, 90 days
│   ├── labeled_leak_events.csv     # 5 real leaks (ground truth)
│   ├── labeled_false_positive_events.csv  # 15 false positives
│   ├── pipeline_segment_metadata.csv
│   ├── gas_composition.csv
│   ├── weather_conditions.csv
│   ├── inspection_history.csv
│   ├── cathodic_protection.csv
│   ├── valve_status.csv            # ⚠️ segment_id is "01" not "SEG-01"
│   ├── row_encroachment.csv
│   └── reference_docs/
├── src/
│   ├── tools/               # Tool functions the agent calls
│   └── agents/              # Agent definitions (Strands SDK)
└── ui/                      # Demo interface (Streamlit)
```

## Key Gotchas
- valve_status.csv uses bare segment_id ("01") while everything else uses "SEG-01". Normalize before joining.
- Don't paste 207K-row SCADA file into agent context. Compute aggregates in code, return summaries only.
- Cap every tool return to <150 words structured output.
- Port 8080 is VS Code. Use 3000+ for dev servers.

## Team Branches
- `data-logic` — Person 1: detection logic and tool functions
- `agent` — Person 2: Strands agent, system prompt, orchestration
- `deploy-ui` — Person 3: Streamlit UI, AgentCore deployment

## Git Sync Rule (ALWAYS FOLLOW THIS)

**Before every task:** run `git pull` to get the latest from all team members.

**After every task:** update your person's PLAN.md and push. Every time.

```
1. git pull
2. Do the work
3. Update collab/personX/PLAN.md with what you did (append, don't overwrite)
4. git add -A
5. git commit with a clear message
6. git push
```

The PLAN.md update should be a short log entry with a timestamp, like:
```
## 2026-09-16 19:30 — Built anomaly detection tool
- Created `src/tools/query_scada.py`
- Tested against 5 labeled leaks, 4/5 detected
- Next: add weather cross-reference
```

**Ask the user which person they are (1, 2, or 3) at the start of every new session** so you update the right PLAN.md.

## Commands
```bash
pip install -r requirements.txt
streamlit run ui/app.py --server.port 3000
agentcore dev --port 3001
```
