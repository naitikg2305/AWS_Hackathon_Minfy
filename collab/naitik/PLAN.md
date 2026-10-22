# Naitik — Data & Detection Logic

Tools: `query_scada`, `check_operational_context`, `locate_leak`

## 2026-10-22 — Minfy hostnames

- ACM cert + `attach-minfy-hostnames.sh`; pipeline.minfytech.com and pipeline-app.minfytech.com live over HTTPS

## 2026-10-21 — Demo website on S3 + CloudFront

- `website/` added from the handoff zip; deploy script; live at https://d1mmotfbiqqghm.cloudfront.net/; Minfy hostname pending IT

## 2026-10-21 — UI on ECS Express Mode (HTTPS)

- Dockerfile + deploy script; ECS Express service live at https://pi-e4a940f7de9544eab171713c4ca21dfd.ecs.us-east-1.on.aws with access-code gate; EC2 box stopped as fallback

## 2026-10-21 — MCP server runtime

- `mcp_server.py` + shared `prompt.py`; second AgentCore runtime (protocol MCP, IAM auth) deployed and smoke-tested; Quick runbook written, Quick not enabled (cost)

## 2026-10-19 — Public UI + agent correctness fix

- Hosted Streamlit on EC2 t4g.micro (public URL), streaming + per-event result cache
- Found the deployed LLM agent classified all 5 leaks as FP (prompt never got the sustained-MBD rule); fixed prompt + UI parser; built `src/tests/eval_agentcore_events.py`; deployed agent now 20/20

## 2026-10-19 — Deployed agent to AgentCore (Minfy R&D account, cost-minimized)

- Installed `@aws/agentcore` CLI, scaffolded `agentcore/` config, registered existing `app/pipeline_leak_agent` as BYO CodeZip Strands agent
- Cost knobs: CodeZip, PUBLIC network, OTel off, 5 min idle / 30 min max lifecycle, no Memory/Gateway/Evals, CSVs in the zip, UI local
- Deployed via CDK (auto-bootstrap), runtime READY, FP-001 smoke test correct in ~31 s
- Reset the account-wide X-Ray indexing rule the CLI set to 100% back to 1%; 7-day log retention
- `model/load.py` → `MODEL_ID` env var; adapter ARN lookup via env/deployed-state; `docs/deploy-agentcore.md` runbook

## 2026-09-16 — Full validation: 20/20 (100%)

- Improved `check_operational_context.py` — wider lookback, better thresholds
- Added `src/tools/validate_all_events.py` — automated test harness
- Detection logic: sustained MBD is primary signal, operational context is informational
- **5/5 leaks detected, 15/15 FPs rejected, avg localization error 5.0 miles**
- FP cause type match 8/15 (remaining mismatches are compressor starts with no explicit SCADA flag)

## 2026-09-16 — Built all 3 tools, tested against labeled events

- Created `src/tools/query_scada.py` — aggregated SCADA summary for station + time window
- Created `src/tools/check_operational_context.py` — compressor/valve/temp disambiguation
- Created `src/tools/locate_leak.py` — pressure gradient localization + valve mapping
- All 3 tested: real leaks correctly have no operational cause + sustained mass balance deficit
- False positives correctly identified (compressor starts, temp line pack)
- Localization accuracy: 0.1-8.4 mile error across 3 tested leaks
