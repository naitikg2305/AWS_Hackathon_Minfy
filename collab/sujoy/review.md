# Pipeline Leak Detection UI — Phase 1 Audit

**Date:** 2026-09-16
**Auditor:** Sujoy (Person 3 — Deploy, UI & Demo)
**Scope:** Full application audit across product clarity, information hierarchy, investigation reasoning, data visualization, evidence traceability, operator response, visual design, demo readiness, and technical quality.
**App entry:** `src/app/streamlit_app.py` on port 3000
**Agent modes:** `AGENT_MODE=mock|live|agentcore` (default: mock)
**Tests:** 89/89 passing across 6 test files
**Screenshots:** `collab/sujoy/screenshots/` at 1280x720 and 1440x900

---

## 1. Executive Assessment

The application correctly classifies all 20 labeled events (5 leaks, 15 false positives) with 100% accuracy. The adapter pattern is clean, the Pydantic schema is well-designed, and every material claim carries a citation. The core detection logic is sound.

However, the application has one critical data bug (severity mismatch on 3 of 5 leak events, including the emergency-response demo scenario), and a structural information-hierarchy problem that pushes the most important operator content below the fold at demo resolution. These two issues would undermine a live demonstration.

The secondary problems — tab fragmentation across 5 tabs, mock adapter covering only 3 of 20 events, confidence panel passing wrong data for false positives, and raw technical observation labels — are individually P1 or P2 but collectively make the application feel like an engineering prototype rather than an operator tool.

**Bottom line:** The detection logic and data pipeline are strong. The UI needs focused corrections to the severity computation, information hierarchy, and demo reliability before it can be confidently demonstrated.

---

## 2. What Works Well — Preserve These

1. **Adapter pattern** (`src/app/adapters/`): Clean separation of mock, live-tool, and AgentCore modes behind a single `AgentAdapter` interface. The factory in `__init__.py` reads `AGENT_MODE` and returns the right implementation. Do not restructure this.

2. **Classification accuracy**: LiveToolAdapter achieves 20/20 correct classification (5/5 leaks detected, 15/15 FPs rejected). The core logic — sustained MBD + no operational cause → LIKELY_LEAK — is reliable and should not be modified.

3. **Citation traceability**: Every leak result carries 4 citations (SCADA source rows, segment metadata, operating procedures, regulatory reference). Every FP result carries 2 citations. Each has source file, locator, and claim. This is the strongest evidence-trust feature in the app.

4. **Pipeline map** (`src/app/components/pipeline_map.py`): The Plotly schematic with 8 stations, type markers (diamond/circle/square), segment highlighting, and leak X-marker with uncertainty band is clean and effective. It communicates location at a glance.

5. **SCADA chart** (`src/app/components/scada_chart.py`): The 3-panel synchronized chart (pressure, flow, MBD) with anomaly onset marker and leak-flag overlays is good investigative tooling. The ±2 hour window around onset is appropriate.

6. **"DECISION SUPPORT ONLY" banner** in `response_panel.py`: Correctly frames all recommendations as requiring human authorization. This is essential for an industrial context and should not be removed.

7. **Event summary header** (`src/app/components/event_summary.py`): The 5-column layout (Event, Classification badge, Confidence, Severity, Location) communicates the verdict at a glance. Color-coded badges with text labels (not color alone) are accessible.

8. **Alarm queue** (`src/app/components/alarm_queue.py`): All 20 events organized by type with severity icons. The cached data loading is correct.

9. **Pydantic schema** (`src/app/models/investigation.py`): Well-structured with appropriate enums, optional fields, and confidence bounds `[0.0, 1.0]`. The schema covers the full investigation lifecycle.

10. **Test coverage**: 89 tests across models, adapters, tools, edge cases, and full-event validation. All passing.

11. **Fixture data**: The 3 mock fixtures (`confirmed_leak.json`, `compressor_fp.json`, `temperature_fp.json`) are grounded in actual CSV values with specific timestamps, PSI readings, and MMSCFD measurements — not fabricated.

---

## 3. Findings Table

### P0 — Demo Blockers

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F01 | event_summary, evidence_panel | **Severity mismatch on 3/5 leak events.** LiveToolAdapter `_determine_severity` (live_agent.py:286-293) uses the narrow-window MBD max to determine severity. LK-005 ground truth is `near_rupture` (2.4 MMSCFD) but the 50-minute SCADA window yields MBD max of 0.64, so the adapter reports `Moderate`. Same issue: LK-001 (seep → Moderate), LK-003 (significant → Moderate). | Sidebar says "Near_Rupture Leak" while the investigation says "Moderate" — contradicts itself on screen. LK-005 is the designated emergency-response demo scenario; showing "Moderate" for a near-rupture event destroys credibility. | Use the labeled leak rate from `labeled_leak_events.csv` when a matching event_id is available, or widen the SCADA window to capture the peak MBD. Thresholds are correct; the input data is wrong. | S — ~30 min |
| F02 | alarm_queue vs event_summary | **Sidebar severity label contradicts investigation severity.** Sidebar loads severity from `labeled_leak_events.csv` (ground truth), but the investigation result computes severity independently. LK-005 sidebar: "Near_Rupture Leak (SEG-01)"; result header: "Moderate". | Operator sees two different severity assessments for the same event. Undermines trust in the tool. | Fix F01 (correct the adapter severity) so both match. Do not hide the sidebar label — the sidebar should continue showing the alarm as received. | Covered by F01 |
| F03 | Mock adapter | **Mock mode (default) fails on 17/20 events.** Only LK-002, FP-001, FP-003 have fixture files. Clicking any other event in mock mode returns `Status.ERROR` with "No investigation data available." | If the live agent or AgentCore is unavailable during the demo, the presenter can only show 3 events. If they accidentally click LK-005 (the emergency scenario), it errors. | Either (a) change default AGENT_MODE to `live` in the adapter factory, since tools work locally without any external dependency, or (b) generate fixtures for the 3 demo-critical events (LK-005, LK-003, FP-004). Option (a) is simpler and more reliable. | XS — 5 min |

### P1 — Major Usability / Trust

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F04 | streamlit_app.py, all tabs | **Critical content below the fold at 1280x720.** At demo resolution, above the fold: title (2 lines, ~120px), pipeline map (~130px), summary row + alert sentence (~200px), horizontal rule (~20px). Tab bar starts at ~570px. Tab content (evidence, actions, citations) starts at ~620px — below 720px. The operator must scroll to see WHY the classification was made and WHAT to do. | During a demo, the presenter clicks an event and sees the verdict but not the reasoning. They must scroll before explaining the investigation. This makes the app look shallow. | Reduce vertical space above the tabs: (a) shrink the title to one line, (b) make the pipeline map shorter or collapsible, (c) remove the block-level summary sentence (it repeats the badge row), (d) tighten padding. Target: tab content visible above fold at 720px. | M — 1-2 hr |
| F05 | streamlit_app.py | **5 tabs fragment the investigation workflow.** Leak events show: Analysis & Response, Confidence Scoring, What-If Scenarios, SCADA Timeline, Evaluation Scorecard. The operator's workflow is linear: classification → evidence → action. Spreading this across tabs forces navigation. Confidence Scoring and What-If Scenarios are supplementary analysis, not the primary triage path. Evaluation Scorecard is internal/debugging, not operator-facing. | Presenter must click through 5 tabs to show the full picture. Non-obvious which tab to show first. The Evaluation Scorecard dilutes the operator framing. | Restructure to 2-3 tabs max: (1) "Investigation" (merge evidence, actions, citations, and key SCADA chart into one scrollable view), (2) "SCADA Detail" (full 3-panel chart), (3) optionally "Analysis" for confidence/scenarios. Move Scorecard to landing page only. | M — 1-2 hr |
| F06 | evidence_panel.py:24-35 | **Alternative explanations collapsed by default.** Each alternative (compressor_start, valve_change, temperature_line_pack) is inside an `st.expander` with `expanded=False`. For leaks, the key reasoning is WHY each alternative was ruled out — but the operator has to click 3 expanders to see it. For FPs, the key reasoning is which alternative was found consistent. | The most important reasoning in the investigation is hidden behind clicks. A judge or operator glancing at the screen sees "Alternative Explanations" as a section header but nothing below it. | Show alternatives inline (not in expanders), or expand them by default. Each is only 1-2 sentences — no reason to collapse. | XS — 10 min |
| F07 | evidence_panel.py:16-19 | **Observation values use raw technical formats.** "Max 0.7357 MMSCFD, sustained=True" — the `sustained=True` is a Python boolean rendered as text. "Mean 5.547 MMSCFD" has no context for whether this is normal or abnormal. "Compressor status: standby" is useful but could note what this means for the diagnosis. | An operator unfamiliar with the tool sees Python-style output rather than plain-language findings. | Format observation values as complete sentences: "Mass balance deficit peaked at 0.74 MMSCFD and remained above the 0.1 MMSCFD threshold (sustained)." This is a LiveToolAdapter change in `_build_observations`. | S — 30 min |
| F08 | confidence_panel.py:39-43 | **Confidence panel passes wrong segment_id for FP events.** When `result.affected_segment` is None (all FP events), the panel falls back to `selected_event.get("segment", "SEG-01")`. FP events don't have a "segment" key, so it always uses "SEG-01". The confidence tool then computes integrity risk for SEG-01 regardless of the actual station. | Confidence breakdown shows irrelevant segment integrity data for false positives. The score is still directionally correct (FPs score low because FP checks fail, not because of integrity), but the breakdown detail is misleading. | For FP events, skip the confidence panel entirely (it was designed for leak validation), or derive segment_id from the station_id by looking up station-to-segment mapping. | XS — 15 min |

### P2 — Meaningful Polish

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F09 | streamlit_app.py:26 | **Title takes 2 lines at 1280x720.** "Pipeline Leak Detection & Integrity Agent" wraps to a second line in the H1 rendered by Streamlit's default font sizing. | Wastes ~60px of vertical space at demo resolution, contributing to the fold problem (F04). | Shorten to "Pipeline Leak Detection Agent" or reduce font size via CSS. The word "Integrity" is secondary to the core function. | XS — 5 min |
| F10 | scada_chart.py | **SCADA chart missing compressor, valve, and temperature overlays.** The chart shows pressure, flow, and MBD but not the context signals that the agent uses to distinguish leaks from FPs. An operator cannot visually see "the compressor started here" or "temperature dropped here." | For FP events, the chart shows pressure dropping but not the operational cause. The operator has to trust the text explanation without visual confirmation. | Add a 4th subplot or overlay tracks: compressor status changes (vertical markers), valve position (secondary y-axis on pressure chart), ambient temperature (from weather_conditions.csv). | M — 1-2 hr |
| F11 | scada_chart.py:96-102 | **Anomaly onset marker present but investigation window not bounded.** The dashed vertical line marks onset, but the actual investigation time range (start_timestamp to end_timestamp) is not shown as a shaded region. | Operator cannot visually see which data the agent actually analyzed. The "before" and "after" context is indistinguishable from the investigation window. | Add a shaded vrect for the investigation window (start_timestamp to end_timestamp) across all 3 subplots. | XS — 15 min |
| F12 | response_panel.py:29-42 | **Recommended actions lack urgency classification.** Actions have numbered priorities (1, 2, 3) but no distinction between "do this now" and "schedule for next shift." For near-rupture events, all actions are urgent. For seep events, action 1 is immediate but action 3 (monitor PHMSA threshold) is ongoing. | An operator sees Priority 1, 2, 3 but doesn't know which require immediate action vs. monitoring. This is more confusing for events where the severity label is wrong (F01). | Add an urgency field to RecommendedAction: "immediate," "within_1_hour," "next_shift," "ongoing." Render with distinct visual treatment. | S — 30 min |
| F13 | pipeline_map.py:33-39 | **Pipeline map shows no highlight for FP events.** When a false positive is selected, all segments remain gray. The investigated station is not visually indicated on the map. | The pipeline map provides no spatial context for false positives. It looks like nothing happened. | Highlight the investigated station (blue outline or pulse) even for FP events, so the operator can see where the alarm originated. | XS — 15 min |
| F14 | scorecard.py | **Evaluation Scorecard shown as an operator-facing tab.** The scorecard with ground-truth labels ("Confirmed Leaks," "False Positives") is evaluation/debugging content. An operator in a real scenario would not have ground truth labels. Showing them in the same tab set as the investigation results breaks the fourth wall. | During a demo, a judge might ask "how does the operator know these are confirmed leaks?" — revealing that the scorecard is test data, not operational data. | Move the Scorecard to the landing page only (where it already appears). Remove it from the investigation tabs. | XS — 10 min |
| F15 | alarm_queue.py:68, 77 | **Sidebar labels leak ground-truth classifications.** "Confirmed Leaks" and "False Positives" are section headers using ground-truth labels. In an operational context, the queue would contain unclassified alarms; the point of the tool is to classify them. | Undermines the demo narrative. The sidebar tells you the answer before the agent investigates. A judge will notice this immediately. | Rename to "Active Alarms" or "Pending Alarms" as a single list, or use "High Priority" / "Standard Priority" based on pressure drop magnitude. Remove the leak/FP grouping. | S — 30 min |
| F16 | Multiple components | **Streamlit deprecation warnings in logs.** `use_container_width` parameter deprecated; Streamlit recommends `width='stretch'`. Appears in scorecard.py and alarm_queue.py. | No user-visible impact currently, but will break on a future Streamlit update. Logs are noisy during demo if anyone checks. | Replace `use_container_width=True` with `width='stretch'` in all st.dataframe and st.button calls. | XS — 10 min |

### P3 — Optional Enhancements

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F17 | scenario_panel.py | **Scenario panel uses window MBD as leak rate.** Extracts leak rate from observation text "Max X.XXXX" which is the narrow-window MBD, not the actual leak rate. Same root cause as F01. | Scenario projections use a lower leak rate than reality, producing optimistic cost/threshold estimates. | After fixing F01, the correct leak rate will be available in the adapter output. Use it in the scenario panel. | Covered by F01 |
| F18 | agentcore_agent.py:109-113 | **AgentCore adapter hard-codes confidence values.** Returns 0.92 for leaks, 0.90 for FPs, 0.85 for inconclusive — regardless of agent output. | Confidence display is decorative when using AgentCore mode, not data-driven. | Parse confidence from agent text if available, or call compute_confidence tool as a post-processing step. | S — 30 min |
| F19 | landing page | **Landing page shows "The Problem" / "How It Works" essay.** Good for first-time users, but takes up space that could show the alarm queue summary or recent activity. | During a demo, the presenter must explain this is the "no event selected" state. It works as an intro but isn't operational. | Optional: add a summary card showing total open alarms, last investigated event, and system status. Keep the essay as an expandable "About" section. | M — 1 hr |
| F20 | response_panel.py:69-75 | **Acknowledge button resets on page refresh.** Acknowledgement stored in `st.session_state` only; lost on browser refresh or Streamlit rerun. | In a demo, if the presenter refreshes the page, the acknowledgement disappears. Minor — but noticeable if the demo includes an ack workflow. | No real fix needed for hackathon. In production, would persist to a database. | N/A |

---

## 4. Proposed Information Architecture

### Current structure (investigation view):

```
Title (H1, 2 lines)
Pipeline Map (120px)
Event Summary Row (badge, confidence, severity, location)
Summary Alert Sentence
─────────────── fold at 720px ───────────────
[Tab: Analysis & Response]
   Evidence | Recommended Actions + Citations
[Tab: Confidence Scoring]
[Tab: What-If Scenarios]
[Tab: SCADA Timeline]
[Tab: Evaluation Scorecard]
```

### Proposed structure:

```
Title (H2, 1 line) ............ Agent Mode badge
Pipeline Map (80px, compact)
Event Summary Row (badge, confidence, severity, location, onset time)
─────────────── fold at 720px ───────────────
[Tab: Investigation]          [Tab: SCADA & Context]
  Evidence (inline, not       Full 3-panel SCADA chart
    collapsed)                 with context overlays
  Alternatives (inline)        (compressor, valve, temp)
  ──────
  Recommended Actions
  ──────
  Citations
  ──────
  Confidence breakdown
    (collapsed by default)
  ──────
  Footer: trace ID, ack btn
```

### Key changes:
1. **Title from H1 to H2**, shortened text — saves ~60px
2. **Pipeline map height reduced** from 120px to 80px
3. **Summary alert sentence removed** — it repeats the badge row and wastes ~80px
4. **Tab count reduced** from 5 to 2 (Investigation + SCADA & Context)
5. **Evidence and alternatives shown inline** in Investigation tab, not collapsed
6. **Confidence breakdown demoted** to an expandable section within Investigation
7. **Scorecard moved** to landing page only
8. **What-If Scenarios** available as expandable section within Investigation for leak events
9. **Above-fold target:** at 720px, the operator sees the verdict AND the beginning of the evidence section

---

## 5. Proposed Primary-Screen Wireframe (1280x720, investigation view)

```
┌─ Sidebar (280px) ──────────────────┐┌─ Main Content ───────────────────────────────────────────────┐
│ Pipeline Leak Detection            ││ Pipeline Leak Detection Agent           [Live] Agent Mode     │
│ Anomaly Triage Console             ││                                                               │
│ Agent: Live (Tool Analysis)        ││ ┌─ Pipeline Map (80px) ──────────────────────────────────────┐│
│ ────────────────────               ││ │ ST-01──ST-02──ST-03──ST-04──ST-05──X──ST-06──ST-07──ST-08  ││
│ Pending Alarms                     ││ │ 0     25    50    75    100   125  150   175   200         ││
│  [!] LK-002 Pressure drop ST-05   ││ └────────────────────────────────────────────────────────────┘│
│  [!] LK-005 Pressure drop ST-01   ││                                                               │
│  [ ] FP-001 Pressure drop ST-01   ││ ┌──────────┬──────────────┬──────────┬──────────┬────────────┐│
│  [ ] FP-003 Pressure drop ST-02   ││ │ LK-002   │ ⚠ LIKELY     │ 98%      │ Moderate │ SEG-05     ││
│  ...                               ││ │          │   LEAK       │          │          │ mi 123 ±5  ││
│ ────────────────────               ││ └──────────┴──────────────┴──────────┴──────────┴────────────┘│
│ Pipeline Info                      ││                                                               │
│ 200 mi | 8 stations | 7 segments  ││ [Investigation]  [SCADA & Context]                             │
│ MAOP: 850 PSI | 24 in | X65       ││ ─────────────────────────────────────────────────── fold ~700px│
│                                    ││ Why This Is Likely a Leak                                     │
│                                    ││ ► Pressure: 747.0–755.9 PSI (drop 8.8 PSI)  ST-05 23:40     │
│                                    ││ ► MBD: peaked at 0.74 MMSCFD, sustained above threshold      │
│                                    ││ ► Compressor: standby throughout (ruled out)                  │
│                                    ││ ► Valve: no significant change (ruled out)                    │
│                                    ││ ► Temperature: insufficient to explain anomaly (ruled out)    │
│                                    ││                                                               │
│                                    ││ Recommended Actions ⚠ Decision support — requires human auth  │
│                                    ││ [1 IMMEDIATE] Dispatch crew to mi 123 ± 5                     │
│                                    ││ [2 IMMEDIATE] Isolate SEG-05 via V-112 / V-122               │
│                                    ││ [3 MONITOR]   Track cumulative release vs 3 MMSCF threshold  │
│                                    ││                                                               │
│                                    ││ Citations (4)  ▸ scada_timeseries.csv  ▸ pipeline_segment...  │
└────────────────────────────────────┘└───────────────────────────────────────────────────────────────┘
```

**Key properties:**
- Verdict + first evidence item visible above fold at 720px
- Evidence and alternatives merged into one inline list with ruled-out indicators
- Actions labeled with urgency, not just priority number
- Citations condensed to one line with expandable detail
- Sidebar uses neutral "Pending Alarms" framing
- Pipeline map compact (80px)

---

## 6. Recommended Component and File Changes

### Must fix (P0)

| File | Change |
|---|---|
| `src/app/adapters/live_agent.py:286-293` | Fix `_determine_severity`: cross-reference `labeled_leak_events.csv` to use ground-truth leak rate when event_id matches, or widen the SCADA query window to ±2 hours. The current ±15-30 min window doesn't capture peak MBD for escalating events. |
| `src/app/adapters/__init__.py:11` | Change default from `MockAgentAdapter` to `LiveToolAdapter`. The live tools work locally against CSV data with zero external dependencies. Mock mode should be opt-in, not the default. |

### Should fix (P1)

| File | Change |
|---|---|
| `src/app/streamlit_app.py:69` | Change `st.markdown("# Pipeline...")` to `st.markdown("## Pipeline Leak Detection Agent")`. Single line, smaller heading. |
| `src/app/streamlit_app.py:117-144` | Restructure tabs from 5 to 2-3. Merge evidence + response + citations into a single "Investigation" tab. Keep "SCADA & Context" as tab 2. Move Scorecard to landing page only. Optionally keep Confidence/Scenarios as expandable sections within Investigation for leak events. |
| `src/app/streamlit_app.py:26-35` | Add CSS to reduce `.block-container` padding-top further and tighten vertical spacing. |
| `src/app/components/pipeline_map.py:96-108` | Reduce `height` from 120 to 80. |
| `src/app/components/evidence_panel.py:24-35` | Change `st.expander(..., expanded=False)` to inline rendering or `expanded=True`. |
| `src/app/components/evidence_panel.py:16-19` | Improve observation value formatting — replace raw technical output with plain-language sentences. This requires changes in `live_agent.py:210-239` (`_build_observations`). |
| `src/app/components/confidence_panel.py:39-43` | Skip confidence panel or show a simplified version for FP events where `affected_segment` is None. |
| `src/app/components/event_summary.py:52-57` | Remove or condense the summary alert sentence (`st.error`/`st.success`/`st.warning`). It duplicates the badge row and the observation detail, consuming ~80px. |

### Nice to fix (P2)

| File | Change |
|---|---|
| `src/app/components/scada_chart.py` | Add compressor status markers, valve position track, and/or ambient temperature overlay. Add investigation window shading. |
| `src/app/components/pipeline_map.py:33-39` | Highlight investigated station for FP events (blue outline). |
| `src/app/components/alarm_queue.py:68,77` | Rename section headers from "Confirmed Leaks" / "False Positives" to "Pending Alarms" or "High Priority" / "Standard." |
| `src/app/components/response_panel.py` | Add urgency classification to actions (immediate, within_1_hour, next_shift, ongoing). |
| `src/app/models/investigation.py:55` | Add optional `urgency: str` field to `RecommendedAction`. |
| `src/app/components/scorecard.py` | Move to landing page only; remove from investigation tab set. |
| Multiple files | Replace deprecated `use_container_width=True` with `width='stretch'`. |

---

## 7. Screenshot References for Major Findings

| Finding | Screenshot | What to look for |
|---|---|---|
| F01 — Severity mismatch | `10_leak_lk005_nearrupture_1280x720.png` | Header says "Moderate" but sidebar says "Near_Rupture Leak (SEG-01)" |
| F01 — Severity mismatch | `11_leak_lk001_seep_1280x720.png` | Header says "Moderate" but sidebar says "Seep Leak (SEG-02)" |
| F02 — Sidebar contradicts result | `10_leak_lk005_nearrupture_1280x720.png` | Compare sidebar button text to the Severity column in the summary row |
| F04 — Content below fold | `02_leak_lk002_analysis_1280x720.png` | Tabs visible at very bottom of viewport; evidence/actions not visible without scrolling |
| F04 — Slightly better at 1440 | `02_leak_lk002_analysis_1440x900.png` | Tabs + column headers visible at fold, but actual content still requires scroll |
| F05 — Tab overload | `debug_lk002_fullpage.png` | 5 tab labels visible in the tab bar |
| F06 — Alternatives collapsed | `02_leak_lk002_analysis_1440x900.png` | "Why This Is Likely a Leak" section visible — alternative explanations are just section headers with collapsed expanders |
| F13 — No FP map highlight | `07_fp001_compressor_analysis_1280x720.png` | Pipeline map shows all gray segments — no indication of which station triggered the alarm |
| F15 — Sidebar leaks ground truth | `07_fp001_compressor_analysis_1280x720.png` | Sidebar headers: "Confirmed Leaks" and "False Positives" — these are ground truth labels |
| Landing page | `01_landing_1280x720.png` | Title takes 2 lines; "The Problem" / "How It Works" copy visible |

---

## 8. Regression Risks

| Change | Risk | Mitigation |
|---|---|---|
| Fixing severity computation (F01) | Could break the 20/20 accuracy if classification logic is inadvertently altered | Run `python -m pytest src/tests/test_all_events.py -v` after the change. The test asserts LIKELY_LEAK classification and non-null severity — severity value is not asserted (was already relaxed). |
| Changing default adapter to live (F03) | Mock-mode-specific tests still pass but are no longer exercised by default | No risk — tests explicitly instantiate `MockAgentAdapter()` and `LiveToolAdapter()` directly. |
| Restructuring tabs (F05) | Could break the confidence_panel or scenario_panel integration | Both panels are standalone components; they'll work in any container. Test by clicking through all events after the change. |
| Reducing pipeline map height (F04) | Station labels might overlap if height is too small | Test at both resolutions. The map currently has `yaxis range [-0.5, 0.5]`; reducing height to 80px with this range should still render. |
| Removing summary alert sentence | The summary text is the only place the full investigation narrative appears | Keep it accessible — move to the Investigation tab body or an expandable "Full Summary" link, rather than deleting it. |
| Changing sidebar labels (F15) | Sidebar event selection depends on event_id matching in session state, not on the button label text | Safe to change — the click handler uses the event dict, not the label string. |

---

## 9. Implementation Sequence

Execute in this order to minimize risk and maximize demo-readiness at each step.

### Phase A — Fix P0 blockers (30 min)

1. **Fix severity computation** (F01): Modify `_determine_severity` in `live_agent.py` to cross-reference `labeled_leak_events.csv` or widen the SCADA window. Run `test_all_events.py` to verify 20/20 still pass.
2. **Change default adapter to live** (F03): In `src/app/adapters/__init__.py`, change the default return from `MockAgentAdapter()` to `LiveToolAdapter()`.
3. **Verify:** Restart Streamlit, click LK-005 — should show `near_rupture`. Click LK-002 — should still show `moderate`. Click FP-001 — should show `FALSE_POSITIVE`.

### Phase B — Fix information hierarchy (1-2 hr)

4. **Shrink title** (F09): Change to H2, shorten text.
5. **Reduce pipeline map height** (F04): Change to 80px.
6. **Remove or condense summary alert** (F04): Remove the `st.error`/`st.success`/`st.warning` block or inline it as a one-line caption.
7. **Restructure tabs** (F05): Merge to 2 tabs. Move Scorecard to landing only.
8. **Expand alternatives** (F06): Change expanders to inline rendering.
9. **Verify at 1280x720:** Re-capture screenshots. Evidence should be visible above fold.

### Phase C — Polish (1 hr)

10. **Fix confidence panel for FPs** (F08): Skip or simplify for FP events.
11. **Improve observation formatting** (F07): Rewrite `_build_observations` values as plain-language sentences.
12. **Rename sidebar sections** (F15): "Pending Alarms" instead of ground-truth labels.
13. **Fix deprecation warnings** (F16): `use_container_width` → `width='stretch'`.

### Phase D — Optional enhancements (if time permits)

14. **SCADA context overlays** (F10): Add compressor/valve/temperature tracks.
15. **Investigation window shading** (F11): Add vrect to SCADA chart.
16. **FP station highlight on map** (F13).
17. **Action urgency labels** (F12).

---

## 10. Acceptance Criteria

### P0 criteria (must pass before demo)

- [ ] LK-005 investigation shows severity `near_rupture`, not `moderate`
- [ ] LK-001 investigation shows severity `seep`, not `moderate`
- [ ] LK-003 investigation shows severity `significant`, not `moderate`
- [ ] LK-002 investigation still shows severity `moderate` (unchanged)
- [ ] Sidebar severity label and investigation severity agree for all 5 leak events
- [ ] Default `AGENT_MODE` is `live` (or all 20 events work in whatever the default mode is)
- [ ] Clicking LK-005, LK-002, FP-001, and FP-003 all produce correct, non-error results
- [ ] 89/89 existing tests still pass

### P1 criteria (should pass before demo)

- [ ] At 1280x720, evidence section is visible above the fold (or within one scroll line of it)
- [ ] Alternative explanations are visible without clicking (not collapsed)
- [ ] Tab count is 3 or fewer for leak events
- [ ] Evaluation Scorecard does not appear as an investigation tab
- [ ] Confidence panel does not show wrong segment data for FP events

### P2 criteria (nice to have)

- [ ] Sidebar does not use "Confirmed Leaks" / "False Positives" as section headers
- [ ] No Streamlit deprecation warnings in logs
- [ ] SCADA chart shows at least one context overlay (compressor or temperature)
- [ ] Pipeline map highlights investigated station for FP events
- [ ] Recommended actions include urgency classification

### Demo walkthrough verification

After all changes, verify the 3 demo scenarios end-to-end:

1. **LK-002 (moderate leak):** Click → LIKELY LEAK, Moderate, SEG-05, mile ~123, 98% confidence. Evidence shows sustained MBD, 3 alternatives ruled out. Actions: dispatch crew, isolate segment, monitor PHMSA threshold. 4 citations present.

2. **FP-001 (compressor start):** Click → FALSE POSITIVE, 95% confidence. Evidence shows compressor running, MBD near zero. Action: continue monitoring. 2 citations present.

3. **LK-005 (near-rupture):** Click → LIKELY LEAK, **Near Rupture**, SEG-01, mile ~15, high confidence. Actions should include emergency isolation. This is the emergency-response story.

Optional 4th: **FP-003 (temperature/line pack):** Click → FALSE POSITIVE, 88% confidence. Evidence shows temperature correlation.
