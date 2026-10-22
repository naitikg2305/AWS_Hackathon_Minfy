# Team Sync Log

All team members: append your updates here after every push so everyone sees the full picture.

---

## 2026-10-22 — Naitik: Minfy hostnames live — pipeline.minfytech.com (website) + pipeline-app.minfytech.com (app)

### What changed
- Prashanth added CNAMEs `pipeline → d1mmotfbiqqghm.cloudfront.net` and `pipeline-app → pi-e4a9….ecs.us-east-1.on.aws` (from Sujoy), then the two ACM validation CNAMEs. One ACM cert (us-east-1) covers both names.
- `website/attach-minfy-hostnames.sh` added the alias + cert to CloudFront and the cert (SNI) + a host-header rule (priority 44991 → our target group) to the shared Express ALB `ecs-express-gateway-alb-bfeb2b96`. ECS Express has no custom-domain setting; the ALB routes by Host, hence the 403/404 before.
- Verified: both URLs HTTPS 200, valid certs, http→https redirect on the website, app health `ok`, headline present.

### For Sujoy
Final links to send: **https://pipeline.minfytech.com/** (demo page + video) and **https://pipeline-app.minfytech.com/** (live app, access code from Naitik).

### Gotcha
After every UI redeploy (`deploy-ui-ecs-express.sh`), run `website/attach-minfy-hostnames.sh` again — Express rolling deployments can swap target groups and the manual host rule must follow.

---

## 2026-10-21 — Naitik: Demo website (handoff zip) hosted on S3 + CloudFront

### What changed
- Sujoy's handoff package (static page "From pipeline alarms to informed decisions" + 5:00 MP4) is now `website/site/` in the repo (checksums match the package) and live at **https://d1mmotfbiqqghm.cloudfront.net/** — HTTPS, HTTP→HTTPS redirect, correct content types incl. `image/avif` and `video/mp4`, byte-range seeking works (206), bucket is private (direct S3 → 403).
- `website/deploy-website.sh` creates/updates everything (bucket, OAC, distribution, invalidation). Cost ≈ $0 (no fixed charge; egress in free tier).
- Reconciled against the live Netlify preview: identical content; only the hero subheading markup differs (classes vs inline styles). Visual check welcome.
- The internal handoff README is NOT in the repo (public). `*.zip` is now gitignored.

### Next (per the handoff)
- IT (Prashanth) to pick the Minfy hostname → `aws acm request-certificate` in us-east-1 → validation CNAME + `CNAME host → d1mmotfbiqqghm.cloudfront.net` → `HOSTNAME_ALIAS=… CERT_ARN=… ./deploy-website.sh`. Then send Sujoy the final URL (handoff says submit Oct 22 for the Nov 3 session).
- Nobody should claim a live Quick integration because the page is up; the page wording already says "illustrative".

---

## 2026-10-21 — Naitik: Public UI moved to ECS Express Mode (HTTPS + access code); EC2 box stopped

### What changed
- New public URL: **https://pi-e4a940f7de9544eab171713c4ca21dfd.ecs.us-east-1.on.aws** (Amazon-issued cert, valid to 2027-05). Shared access code in front (ask Naitik); the `APP_PASSWORD` gate in `streamlit_app.py`.
- `agentcore-deploy/ui-ecs-express/`: `Dockerfile` (python:3.12-slim, Streamlit on 8080, non-root, no AWS keys) + `deploy-ui-ecs-express.sh` (podman build → ECR `pipeline-leak-ui` → `aws ecs create/update-express-gateway-service`). ECS Express provisions Fargate + ALB + TLS + URL itself.
- IAM: task role `pipeline-leak-ui-task-role` (InvokeAgentRuntime only), infra role `pipeline-leak-ui-express-infra-role` (AWS managed Express policy). The other team's `ecsInfrastructureRoleForExpressServices` can't be assumed by Express (its trust has a SourceArn condition) — don't reuse it.
- EC2 box `i-0fe15135262c099ed` (http://54.144.59.20/) terminated, Elastic IP released, security group deleted; `agentcore-deploy/ui-ec2/` kept only as the fallback recipe. Only the ECS Express URL is live now.

### Cost
~$35/mo running (Fargate ~$18 + ALB ~$16) vs ~$10 for the EC2 box. HTTPS is the reason. Scale to zero between demo days: see the script's printed command; the ALB bills until the service is deleted.

### Next
- Ask IT for a Minfy subdomain → CNAME to the ALB + ACM cert; then Streamlit `st.login` (OIDC) against Entra for real sign-in.

---

## 2026-10-21 — Naitik: Agent is now also an MCP server (deployed, IAM auth); Amazon Quick NOT connected

### What changed
- New runtime `pipeline_leak_mcp` (`pipelineleakagent_pipeline_leak_mcp-8R09966rG3`, protocol MCP, IAM auth) from `agentcore-deploy/.../mcp_server.py`. Tools: `investigate_pipeline_event(station_id, start_time, end_time, event_id="")` (runs the validated agent, returns the verdict text) and `list_alarm_events(kind)`.
- System prompt moved to `prompt.py`, shared by `main.py` (HTTP runtime for the UI) and `mcp_server.py`. One place to edit; re-run `src/tests/eval_agentcore_events.py` after changes.
- `pyproject.toml`: `mcp>=1.10,<2` (mcp 2.x renamed FastMCP → MCPServer; AgentCore docs use the 1.x API).
- Smoke: `src/tests/smoke_mcp_runtime.py` (JSON-RPC via boto3 `invoke_agent_runtime`): initialize OK, tools/list OK, `list_alarm_events` 7.5 s cold, `investigate_pipeline_event(FP-001)` 23 s → FALSE POSITIVE.
- Same cost profile as the HTTP runtime: CodeZip, PUBLIC, OTel off, 5/30 min lifecycle; bills only while a call runs.

### Amazon Quick
- Decision: not enabling Quick (Professional/Enterprise = $250/account/month flat + $20–40/user; trial auto-converts). The MCP server is ready for it; what remains is a Cognito pool + flipping this runtime's `authorizerType` to `CUSTOM_JWT` + registering the endpoint in Quick. Runbook: `docs/quick-mcp-integration.md`.
- Repo hygiene: `agentcore-deploy/.../mcp_client/` is unused CLI boilerplate and `presentation.md:362` claims an "MCP client integration" — now we really have an MCP *server*; update the slide wording.

---

## 2026-10-19 — Naitik: Agent was calling all 5 leaks FALSE POSITIVE — fixed, 20/20 on the deployed agent

### What happened
- Public UI (http://54.144.59.20/, `AGENT_MODE=agentcore`) showed every confirmed leak as a false positive. Root cause: the LLM system prompt still said "temperature drop explains it → FALSE POSITIVE", and `check_operational_context` flags temperature on nearly every event (12 h lookback). Sujoy's fix (sustained MBD beats temperature-only) only lived in `live_agent.py`. The hackathon demo ran `AGENT_MODE=live`, so the agent was never validated end to end.
- Second bug: `agentcore_agent.py` classified FALSE_POSITIVE if the phrase appeared anywhere in the text (e.g. "not a false positive").

### What changed
- System prompt: validated decision rule + severity thresholds from `live_agent.py`; answer must start with `CLASSIFICATION: ...` / `SEVERITY: ...`; ~350-word cap (FP 30 s → 20 s, leak 66 s → 30 s).
- Adapter parses the verdict line; severity regex fixed. UI streams the agent's text live and caches results per event for 2 h ("Re-run live agent" bypasses).
- New `src/tests/eval_agentcore_events.py`: runs labeled events through the deployed runtime in parallel. **Result: 20/20 classification correct.** Severity exact on LK-003/LK-004; LK-001 and LK-002 graded one step too high, LK-005 graded significant instead of near_rupture (see Open).

### Open
- Severity: the UI window is onset−15 min … +30 min, so `max_mmscfd`/`drop_psi` in that window may not reach the near_rupture thresholds for LK-005; check `query_scada` numbers vs the thresholds in `_determine_severity` and align prompt + live adapter.
- Public URL has no auth; stop the EC2 box between demo days.

---

## 2026-10-19 — Naitik: Agent deployed to AgentCore in the Minfy R&D account (cost-minimized)

### What changed
- Runtime `pipelineleakagent_pipeline_leak_agent-xYeQ4WBuf7` is READY in the Minfy R&D account (us-east-1, profile `minfy-rnd`). Stack `AgentCore-pipelineleakagent-default` = 1 IAM role + 1 policy + 1 Runtime. Nothing else.
- Smoke test: FP-001 → FALSE POSITIVE (temperature line pack) with full evidence chain, ~31 s.
- `agentcore-deploy/pipelineleakagent/agentcore/agentcore.json` committed (was gitignored). CodeZip, PUBLIC, OTel off, 5 min idle / 30 min max, `MODEL_ID` env var (Sonnet 4.5).
- `model/load.py` reads `MODEL_ID`; `src/app/adapters/agentcore_agent.py` no longer hardcodes the lab-account ARN (env var → `agentcore/.cli/deployed-state.json`).
- New runbook `docs/deploy-agentcore.md` with redeploy/invoke/teardown commands and the cost table.

### For Sujoy (UI)
`AWS_PROFILE=minfy-rnd AGENT_MODE=agentcore streamlit run src/app/streamlit_app.py --server.port 3000` should now hit the live runtime. I only tested `agentcore invoke`, not the SSE parsing in the adapter — please check.

### For Sriram (Agent)
Still Sonnet 4.5. If you want to try Haiku 4.5 for cost, change `MODEL_ID` in `agentcore.json` and redeploy, then re-run the 20 events.

### Open
- Run all 20 labeled events against the deployed runtime.
- Teardown after the hackathon: `agentcore remove agent --name pipeline_leak_agent && agentcore deploy -y`.

---

## 2026-09-16 — Sujoy: Fixed regression from ground truth removal, updated audit

### What changed
- **REGRESSION FIX**: Sriram's ground truth removal exposed a latent bug — `check_operational_context`'s 12-hour temperature lookback always triggers for all events (diurnal swings >15°F). Fixed `live_agent.py` to distinguish mechanical causes (compressor/valve) from temperature-only: sustained localized MBD overrides temperature explanation. All 20/20 still pass.
- **Test fix**: Updated `test_tools.py` to use new `sustained_above_0.15` key (was `has_leak_flag` which was removed)
- **Updated `collab/sujoy/review.md`** — Re-audited against latest codebase. Added RESOLVED section for 5 fixed issues. Remaining: 3 P0, 4 P1, 8 P2, 4 P3.
- 89/89 tests passing, 20/20 batch scorecard

### For Sriram
Your ground truth removal was correct and important. The temperature interaction needed one more adapter fix — now done. The `check_operational_context` tool itself is fine; the adapter just needed to weight mechanical causes higher than temperature-only for sustained deficits.

### For Naitik
No changes to your tools or AgentCore deployment.

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
