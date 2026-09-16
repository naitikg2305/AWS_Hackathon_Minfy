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

## Commands
```bash
pip install -r requirements.txt
streamlit run ui/app.py --server.port 3000
agentcore dev --port 3001
```
