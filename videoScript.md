# Pipeline Leak Detection Agent — 3-Minute Video Script

**Target:** 3:00 | **Pace:** ~150 words/min spoken | **Format:** Screen recording with voiceover
**Judging criteria to hit:** (1) Agentic behavior — tool calls, autonomous reasoning (2) Source code integrity — no shortcuts, no faked data (3) UI/UX quality (4) AgentCore deployment and usage

---

## [0:00–0:25] THE PROBLEM (25 sec)

**SCREEN:** Landing page of the Streamlit app — pipeline map visible, "The Problem" / "How It Works" sections.

**NARRATION:**
"A gas pipeline operator monitors 200 miles of pipeline through 8 SCADA stations, generating over 200,000 readings across 90 days. When pressure drops, it could be a real leak — or a compressor starting, a valve moving, or cold weather shrinking the gas. A missed leak costs millions in penalties and repair. An unnecessary shutdown costs over $100K. Rule-based alarms can't tell the difference. Our agent can."

---

## [0:25–1:05] THE AGENT IN ACTION — Leak Detection (40 sec)

**SCREEN:** Click **LK-002** in sidebar. Show spinner "Investigating event LK-002..." Then the result loads.

**NARRATION:**
"When an operator selects an alarm, the agent investigates autonomously. It's not a lookup — it's a Strands agent with 8 tools running on Claude Sonnet 4.5."

**SCREEN:** Point to the classification badge (LIKELY LEAK), confidence (94%), severity (Moderate), location (SEG-05, mile 119).

**NARRATION:**
"The agent classified this as a likely leak with 94% confidence on segment 5, mile 119. Let me show you HOW it reached that conclusion."

**SCREEN:** Scroll to evidence panel — observations showing pressure drop, sustained mass balance deficit, compressor standby, valve stable.

**NARRATION:**
"It queried SCADA data, found a sustained mass balance deficit of 0.74 MMSCFD, then checked for operational explanations — compressor starts, valve changes, temperature effects. All three were ruled out. No operational cause plus sustained deficit equals likely leak."

**SCREEN:** Show alternative explanations — all three marked "Ruled Out" with green checkmarks.

**NARRATION:**
"Every alternative is explicitly evaluated and ruled out. This is the contextual reasoning that rule-based alarms cannot do."

---

## [1:05–1:30] RESPONSE AND COMPLIANCE (25 sec)

**SCREEN:** Show response panel — recommended actions with priority levels, citations panel.

**NARRATION:**
"For confirmed leaks, the agent recommends specific actions: dispatch a crew to mile 119, isolate the segment via valves V-112 and V-122, and monitor cumulative gas loss against the PHMSA 3 million cubic feet reporting threshold. Every recommendation cites a specific operating procedure or regulation."

**SCREEN:** Point to citations — scada_timeseries.csv, pipeline_segment_metadata.csv, pipeline_operating_procedures.md, 49 CFR 191.5.

**NARRATION:**
"Four citations trace every claim back to the actual data source — SCADA rows, segment metadata, operating procedures, and federal regulations. Nothing is made up."

---

## [1:30–1:55] FALSE POSITIVE DISAMBIGUATION (25 sec)

**SCREEN:** Click **FP-001** in sidebar. Wait for result. Show FALSE POSITIVE badge with green checkmark.

**NARRATION:**
"Now watch how the same agent handles a false positive. FP-001 had a 14 PSI pressure drop at station 1 — similar magnitude to a real leak. But the agent found a compressor start in the operational context, mass balance deficit near zero, and pressure recovered within 25 minutes. It classified this as a false positive and recommended continuing normal monitoring — saving the operator a $100K shutdown."

---

## [1:55–2:20] DATA-DRIVEN CONFIDENCE AND WHAT-IF SCENARIOS (25 sec)

**SCREEN:** Click back to **LK-002**, then click the **Confidence Scoring** tab. Show the score gauge and 4 signal breakdowns.

**NARRATION:**
"Our confidence scores aren't LLM-estimated — they're computed from 4 measurable signals. False positive checks clear: 100%. Deficit persistence: high. Leak rate severity: 75%. Segment integrity risk from inspection history. Each signal reads directly from the data files."

**SCREEN:** Click **What-If Scenarios** tab. Show the 4 scenario cards — continue, double, escalate, isolate.

**NARRATION:**
"The what-if engine projects outcomes: if this leak continues for 48 hours, cumulative gas loss hits the PHMSA threshold. Cost of delay versus isolating now — quantified in dollars so the operator can make an informed decision."

---

## [2:20–2:40] SOURCE CODE INTEGRITY (20 sec)

**SCREEN:** Switch to IDE/terminal. Show the tools directory listing, then briefly show `query_scada.py` reading from CSV, `compute_confidence.py` computing from 4 data sources.

**NARRATION:**
"Every tool computes from real data — 207,000 SCADA rows, weather conditions, inspection history, cathodic protection readings. Zero hardcoded responses, zero event-ID matching. Operating envelope ranges are derived from 5th-to-95th percentile SCADA baselines, not lookup tables. Gas costs come from the composition CSV. We audited the code and removed all ground truth leakage from the classification path."

**SCREEN:** Run `python -m src.batch_scorecard` — show "20/20 (100%)" result. Then `python -m pytest src/tests/ -q` — show "89 passed."

**NARRATION:**
"Twenty out of twenty events classified correctly — five real leaks detected, fifteen false positives rejected. Eighty-nine automated tests passing."

---

## [2:40–3:00] AGENTCORE DEPLOYMENT (20 sec)

**SCREEN:** Show terminal with AgentCore runtime ARN. Show architecture diagram from rubric.md or a quick view of `agentcore_agent.py` invoking the runtime.

**NARRATION:**
"The agent is fully deployed to Amazon Bedrock AgentCore — CodeZip package with all 6 tools and bundled data, running Claude Sonnet 4.5, streaming responses via SSE. The Streamlit UI calls it through a boto3 adapter with a single environment variable toggle between local tools and the deployed runtime. Same system prompt, same tools, same behavior — local or cloud."

**SCREEN:** Show the `AGENT_MODE=agentcore` environment variable and the adapter factory code.

**NARRATION:**
"Three team members, one agent, eight tools, zero shortcuts. Pipeline Leak Detection and Integrity Agent."

---

## Production Notes

**Key moments to nail on screen:**
- The spinner → result load for LK-002 (shows the agent actually doing work, not a cached lookup)
- The "Ruled Out" badges on alternative explanations (shows reasoning depth)
- The citations panel (shows grounding — judges will look for this)
- The FP-001 contrast (shows the agent adapts, not just a leak detector)
- The batch scorecard terminal output (shows systematic evaluation)
- The AgentCore ARN and runtime status (proves deployment is real)

**What NOT to do:**
- Don't click events that error in mock mode — use live mode (`AGENT_MODE=live`)
- Don't dwell on the landing page essay — get to the investigation fast
- Don't show the Evaluation Scorecard tab during investigation (it reveals ground truth labels)
- Don't scroll past the fold at 1280x720 without narrating — acknowledge the content is below

**Fallback if AgentCore is down:**
- Demo in live mode (tools run locally against CSV data)
- Mention AgentCore deployment with ARN and show the adapter code
- Show `rubric.md` section 4 which documents the deployment status

**Recording settings:**
- Resolution: 1440x900 (better than 1280x720 for visibility)
- Browser: Chrome, dark mode matches Streamlit dark theme
- Terminal: split screen or picture-in-picture for code segments
- Start Streamlit with: `AGENT_MODE=live streamlit run src/app/streamlit_app.py --server.port 3000`
