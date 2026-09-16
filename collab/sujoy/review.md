# Pipeline Leak Detection UI — Phase 1 Audit (Updated)

**Date:** 2026-09-16 (updated after latest teammate pull)
**Auditor:** Sujoy (Person 3 — Deploy, UI & Demo)
**Scope:** Full application audit across product clarity, information hierarchy, investigation reasoning, data visualization, evidence traceability, operator response, visual design, demo readiness, and technical quality.
**App entry:** `src/app/streamlit_app.py` on port 3000
**Agent modes:** `AGENT_MODE=mock|live|agentcore` (default: mock)
**Tests:** 89/89 passing across 6 test files
**Batch scorecard:** 20/20 (100%) — 5/5 leaks, 15/15 FPs, avg confidence 81%
**Screenshots:** `collab/sujoy/screenshots/` at 1280x720 and 1440x900

---

## 1. Executive Assessment

The application correctly classifies all 20 labeled events (5 leaks, 15 false positives) with 100% accuracy. The adapter pattern is clean, the Pydantic schema is well-designed, and every material claim carries a citation. The core detection logic is sound.

**Regression found and fixed this session:** Sriram's latest changes removed ground truth leakage from `query_scada` (correctly), but the removal of `has_leak_flag` exposed a latent bug — the `check_operational_context` tool's 12-hour temperature lookback always finds a >15°F diurnal swing, causing all 5 leak events to be misclassified as FALSE_POSITIVE via the LiveToolAdapter. Fixed in `live_agent.py` by distinguishing mechanical causes (compressor/valve) from temperature-only causes: a sustained localized MBD overrides temperature explanations because temperature affects all segments equally while leaks are localized. All 89 tests now pass.

**Remaining critical issues:** The severity mismatch on 3/5 leak events (including the emergency-response demo scenario LK-005) persists. The sidebar still uses ground truth labels ("Confirmed Leaks"/"False Positives"). The default `AGENT_MODE` is still `mock`, which only serves 3/20 events.

**New context from `rubric.md`:** The judging rubric confirms 4 evaluation dimensions: (1) Agentic Behavior, (2) Source Code Integrity, (3) Video/UI/UX, (4) AgentCore Usage. The rubric already marks the solution as PASS on all 4 dimensions. Our UI findings primarily affect dimension 3 (UI/UX polish) and indirectly affect how credibly we present dimension 2 (source integrity — the sidebar ground truth labels undermine the "no hardcoded responses" claim).

---

## 2. What Works Well — Preserve These

1. **Adapter pattern** (`src/app/adapters/`): Clean separation of mock, live-tool, and AgentCore modes behind a single `AgentAdapter` interface. The factory in `__init__.py` reads `AGENT_MODE` and returns the right implementation. Do not restructure this.

2. **Classification accuracy**: LiveToolAdapter achieves 20/20 correct classification (5/5 leaks detected, 15/15 FPs rejected). The core logic — sustained MBD + no mechanical operational cause → LIKELY_LEAK — is reliable and should not be modified.

3. **Ground truth leakage removal** (NEW): Sriram's latest code review removed all ground truth leakage: `has_leak_flag` from query_scada, `event_flags` exposure, FP label checks in compute_confidence, and hardcoded operating envelope values. Classification is now fully data-driven.

4. **Citation traceability**: Every leak result carries 4 citations (SCADA source rows, segment metadata, operating procedures, regulatory reference). Every FP result carries 2 citations. Each has source file, locator, and claim.

5. **Pipeline map** (`src/app/components/pipeline_map.py`): Updated — now reads station types from SCADA data dynamically. The Plotly schematic with 8 stations, type markers (diamond/circle/square), segment highlighting, and leak X-marker with uncertainty band is clean and effective.

6. **SCADA chart** (`src/app/components/scada_chart.py`): Updated — improved column selection, transparent backgrounds, better subtitle formatting. The 3-panel synchronized chart (pressure, flow, MBD) with anomaly onset marker and leak-flag overlays is good.

7. **"DECISION SUPPORT ONLY" banner** in `response_panel.py`: Correctly frames all recommendations as requiring human authorization. Essential for industrial context.

8. **Event summary header** (`src/app/components/event_summary.py`): 5-column layout (Event, Classification badge, Confidence, Severity, Location) communicates the verdict at a glance. Color-coded badges with text labels are accessible.

9. **Confidence scoring** (`src/app/components/confidence_panel.py`): Correctly calls `compute_confidence` tool in real time. Updated compute_confidence now checks system-wide deficit (not FP label lookup). 4th check is physics-grounded.

10. **Scenario projections** (`src/app/components/scenario_panel.py`): Gas cost now derived from `gas_composition.csv` (not hardcoded). Constants have source citations.

11. **Operating envelope** (`src/tools/lookup_operating_envelope.py`): Rewritten to compute 5th-95th percentile pressure/flow ranges from SCADA baseline data, reading MAOP from segment metadata. No longer hardcoded.

12. **Pydantic schema** (`src/app/models/investigation.py`): Well-structured with appropriate enums, optional fields, and confidence bounds `[0.0, 1.0]`.

13. **Test coverage**: 89 tests across 6 files (models, adapters, tools, edge cases, full-event validation). All passing.

14. **Rubric documentation** (NEW): `rubric.md` provides self-assessment against judging criteria with architecture diagram and key file references.

---

## 3. Findings Table

### P0 — Demo Blockers

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F01 | event_summary, evidence_panel | **Severity mismatch on 3/5 leak events.** LiveToolAdapter `_determine_severity` (live_agent.py:288-295) uses the narrow-window MBD max. LK-005 ground truth is `near_rupture` (2.4 MMSCFD) but the ±15-30min SCADA window yields MBD max of ~0.64, so adapter reports `Moderate`. Same: LK-001 (seep → Moderate), LK-003 (significant → Moderate). | Sidebar says "Near_Rupture Leak" while investigation says "Moderate" — contradicts itself on screen. LK-005 is the emergency-response demo; showing "Moderate" for near-rupture destroys credibility. | Widen the SCADA query window for the severity calculation, or use a rate-of-change extrapolation. The thresholds themselves are correct; the input data window is too narrow. | S — ~30 min |
| F02 | alarm_queue vs event_summary | **Sidebar severity label contradicts investigation severity.** Sidebar loads from `labeled_leak_events.csv` (ground truth) but investigation computes independently. LK-005 sidebar: "Near_Rupture Leak (SEG-01)"; result header: "Moderate". | Operator sees two different severity assessments. Undermines trust. | Fix F01 (correct the adapter severity) so both match. | Covered by F01 |
| F03 | Mock adapter | **Mock mode (default) fails on 17/20 events.** Only LK-002, FP-001, FP-003 have fixture files. Clicking any other event in mock mode returns `Status.ERROR`. | If live tools unavailable during demo, only 3 events work. If presenter clicks LK-005, it errors. | Change default `AGENT_MODE` to `live` in `src/app/adapters/__init__.py`. Live tools work locally against CSV data with zero external dependencies. | XS — 5 min |

### P1 — Major Usability / Trust

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F04 | streamlit_app.py, all tabs | **Critical content below the fold at 1280x720.** Above the fold: title (~120px), pipeline map (~130px), summary row + alert sentence (~200px), horizontal rule (~20px). Tab bar starts at ~570px. Tab content starts at ~620px — below 720px. Operator must scroll to see WHY and WHAT TO DO. | During demo, presenter clicks event and sees verdict but not reasoning. Must scroll before explaining. Makes app look shallow. | Reduce vertical space: (a) shrink title to one line, (b) reduce pipeline map height, (c) remove block-level summary sentence (repeats badge row), (d) tighten padding. Target: tab content visible above fold at 720px. | M — 1-2 hr |
| F05 | streamlit_app.py | **5 tabs fragment the investigation workflow.** Leak events: Analysis & Response, Confidence Scoring, What-If Scenarios, SCADA Timeline, Evaluation Scorecard. Operator workflow is linear (classification → evidence → action). Spreading across tabs forces navigation. Scorecard is internal/debugging, not operator-facing. | Presenter must click through 5 tabs. Non-obvious which to show first. Scorecard dilutes operator framing. | Restructure to 2-3 tabs: (1) "Investigation" (evidence + actions + citations + key chart), (2) "SCADA Detail" (full 3-panel chart), (3) optionally "Analysis" for confidence/scenarios. Move Scorecard to landing page only. | M — 1-2 hr |
| F06 | evidence_panel.py:34 | **Alternative explanations collapsed by default.** Each alternative (compressor_start, valve_change, temperature_line_pack) inside `st.expander` with `expanded=False`. For leaks, the key reasoning is WHY each was ruled out — but operator has to click 3 expanders. | Most important reasoning hidden behind clicks. Judge sees "Alternative Explanations" header but nothing below it. | Show alternatives inline (not in expanders), or expand by default. Each is 1-2 sentences. | XS — 10 min |
| F07 | evidence_panel.py:16-19 | **Observation values use raw technical formats.** "Max 0.7357 MMSCFD, sustained=True" — Python boolean as text. "Mean 5.547 MMSCFD" with no context for normal/abnormal. | Operator sees Python-style output rather than plain-language findings. | Format as complete sentences: "Mass balance deficit peaked at 0.74 MMSCFD and remained above threshold (sustained)." This is a LiveToolAdapter change in `_build_observations`. | S — 30 min |
| F08 | confidence_panel.py:51 | **Confidence panel passes wrong segment_id for FP events.** When `result.affected_segment` is None (all FPs), falls back to `selected_event.get("segment", "SEG-01")`. FP events lack "segment" key → always SEG-01. Confidence tool then computes integrity risk for wrong segment. | Score is still directionally correct (FPs score low because FP checks fail), but breakdown detail is misleading for wrong segment. | For FP events, derive segment_id from station_id via segment metadata lookup, or skip integrity signal display. | XS — 15 min |

### P2 — Meaningful Polish

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F09 | streamlit_app.py:71 | **Title takes 2 lines at 1280x720.** "Pipeline Leak Detection & Integrity Agent" wraps in H1. | Wastes ~60px, contributing to fold problem (F04). | Shorten to "Pipeline Leak Detection Agent" or use H2 + CSS. | XS — 5 min |
| F10 | scada_chart.py | **SCADA chart missing compressor, valve, and temperature overlays.** Shows pressure, flow, MBD but not context signals the agent uses to distinguish leaks from FPs. | For FP events, chart shows pressure dropping but not the operational cause. Operator must trust text without visual confirmation. | Add compressor status markers, valve position track, and/or ambient temperature overlay. | M — 1-2 hr |
| F11 | scada_chart.py:96-102 | **Investigation window not visually bounded.** Dashed onset line present, but actual investigation time range (start to end) not shown as shaded region. | Operator cannot see which data the agent analyzed vs. surrounding context. | Add shaded vrect for investigation window across all 3 subplots. | XS — 15 min |
| F12 | response_panel.py:29-42 | **Actions lack urgency classification.** Priority 1/2/3 but no "do now" vs "schedule for next shift" distinction. Near-rupture: all urgent. Seep: action 3 is ongoing monitoring. | Operator sees Priority 1,2,3 but not which require immediate action. | Add urgency field: "immediate," "within_1_hour," "next_shift," "ongoing." | S — 30 min |
| F13 | pipeline_map.py:93 | **Pipeline map shows no highlight for FP events.** When FP selected, all segments gray. Investigated station not indicated. | Pipeline map provides no spatial context for false positives. | Highlight investigated station (blue outline) even for FP events. | XS — 15 min |
| F14 | scorecard.py | **Evaluation Scorecard shown as operator-facing tab.** Scorecard with ground-truth labels is evaluation content. Operators would not have ground truth. | Judge might ask "how does operator know these are confirmed leaks?" — reveals test data framing. | Move Scorecard to landing page only. Remove from investigation tabs. | XS — 10 min |
| F15 | alarm_queue.py:68, 76 | **Sidebar labels leak ground-truth classifications.** "Confirmed Leaks" and "False Positives" as section headers. In operational context, queue would contain unclassified alarms. **Rubric impact:** undermines "no hardcoded responses" claim since the sidebar reveals answers before the agent investigates. | Sidebar tells you the answer before investigation. Judge will notice immediately. | Rename to "Active Alarms" or "Pending Alarms" as a single list, or "High Priority" / "Standard Priority" based on pressure drop magnitude. | S — 30 min |
| F16 | Multiple components | **Streamlit deprecation warnings.** `use_container_width` deprecated; Streamlit recommends newer API. Appears in pipeline_map.py:130, response_panel.py:73, alarm_queue.py:73,80. | No user-visible impact currently. Noisy logs during demo. | Update to current Streamlit API. | XS — 10 min |

### P3 — Optional Enhancements

| # | Screen / Component | Problem | Operator / Demo Impact | Recommended Correction | Effort |
|---|---|---|---|---|---|
| F17 | scenario_panel.py:62-67 | **Scenario panel uses window MBD as leak rate.** Extracts from observation text "Max X.XXXX" which is the narrow-window MBD, not actual leak rate. Same root as F01. | Scenario projections use a lower rate than reality, producing optimistic estimates. | After fixing F01, correct rate will be available. | Covered by F01 |
| F18 | agentcore_agent.py:109-113 | **AgentCore adapter hard-codes confidence values.** Returns 0.92 for leaks, 0.90 for FPs, 0.85 for inconclusive — regardless of agent output. | Confidence display is decorative in AgentCore mode. | Parse confidence from agent text or call compute_confidence as post-processing. | S — 30 min |
| F19 | landing page | **Landing page shows essay text.** Good for first-time users, takes space. | Presenter must explain "no event selected" state. Works as intro but isn't operational. | Optional: add summary card (open alarms, last investigated, system status). Keep essay as expandable. | M — 1 hr |
| F20 | response_panel.py:70-75 | **Acknowledge button resets on page refresh.** Stored in `st.session_state` only. | Minor — if presenter refreshes, ack disappears. | No fix needed for hackathon. Production would persist to DB. | N/A |

### RESOLVED (since last audit)

| # | What Changed | Resolution |
|---|---|---|
| R01 | **Ground truth leakage in classification path** | Sriram removed `has_leak_flag` from query_scada, classification logic in live_agent.py, and FP label lookup from compute_confidence. Verified: `live_agent.py` line 79 uses only `mbd_sustained` and mechanical cause check. |
| R02 | **Operating envelope hardcoded** | `lookup_operating_envelope.py` rewritten to compute 5th-95th percentile from SCADA baseline data. |
| R03 | **Gas cost hardcoded** | `simulate_scenario.py` now derives cost from `gas_composition.csv` heating values × Henry Hub price. |
| R04 | **FP check used ground truth labels** | `compute_confidence.py` 4th check replaced with system-wide deficit analysis (physics-grounded, not label-based). |
| R05 | **Temperature-only cause misclassifying leaks** | Fixed this session: `live_agent.py` now distinguishes mechanical causes (compressor/valve) from temperature-only. Sustained localized MBD overrides temperature explanation. All 20/20 events still correct. |

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
3. **Summary alert sentence removed** — repeats badge row
4. **Tab count reduced** from 5 to 2 (Investigation + SCADA & Context)
5. **Evidence and alternatives shown inline** in Investigation tab
6. **Confidence breakdown demoted** to expandable section within Investigation
7. **Scorecard moved** to landing page only
8. **What-If Scenarios** as expandable section within Investigation for leaks
9. **Above-fold target:** at 720px, operator sees verdict AND beginning of evidence

---

## 5. Proposed Primary-Screen Wireframe (1280x720)

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
│  [ ] FP-003 Pressure drop ST-02   ││ │ LK-002   │ ⚠ LIKELY     │ 94%      │ Moderate │ SEG-05     ││
│  ...                               ││ │          │   LEAK       │          │          │ mi 119 ±5  ││
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
│                                    ││ [1 IMMEDIATE] Dispatch crew to mi 119 ± 5                     │
│                                    ││ [2 IMMEDIATE] Isolate SEG-05 via V-112 / V-122               │
│                                    ││ [3 MONITOR]   Track cumulative release vs 3 MMSCF threshold  │
│                                    ││                                                               │
│                                    ││ Citations (4)  ▸ scada_timeseries.csv  ▸ pipeline_segment...  │
└────────────────────────────────────┘└───────────────────────────────────────────────────────────────┘
```

---

## 6. Recommended Component and File Changes

### Must fix (P0)

| File | Change |
|---|---|
| `src/app/adapters/live_agent.py:288-295` | Fix `_determine_severity`: widen the SCADA query window to ±2 hours for severity determination, or use rate-of-change extrapolation. Current ±15-30 min window doesn't capture peak MBD for escalating events. |
| `src/app/adapters/__init__.py:10` | Change default from `MockAgentAdapter` to `LiveToolAdapter`. Live tools work locally against CSV data with zero external dependencies. Mock should be opt-in. |

### Should fix (P1)

| File | Change |
|---|---|
| `src/app/streamlit_app.py:71` | Change `st.markdown("# Pipeline...")` to `st.markdown("## Pipeline Leak Detection Agent")`. Single line. |
| `src/app/streamlit_app.py:129-144` | Restructure tabs from 5 to 2-3. Merge evidence + response + citations into "Investigation." Keep "SCADA & Context." Move Scorecard to landing only. |
| `src/app/streamlit_app.py:26-35` | Add CSS to reduce padding and tighten vertical spacing. |
| `src/app/components/pipeline_map.py:115` | Reduce `height` from 120 to 80. |
| `src/app/components/evidence_panel.py:34` | Change `expanded=False` to `expanded=True` or inline rendering. |
| `src/app/components/evidence_panel.py:16-19` | Improve observation value formatting. Requires changes in `live_agent.py` `_build_observations`. |
| `src/app/components/confidence_panel.py:51` | For FP events, derive segment_id from station_id via segment metadata, or skip integrity signal display. |

### Nice to fix (P2)

| File | Change |
|---|---|
| `src/app/components/scada_chart.py` | Add compressor status markers, valve position track, ambient temperature overlay. Add investigation window shading. |
| `src/app/components/pipeline_map.py:93` | Highlight investigated station for FP events (blue outline). |
| `src/app/components/alarm_queue.py:68,76` | Rename "Confirmed Leaks"/"False Positives" to "Pending Alarms" or "High Priority"/"Standard." |
| `src/app/components/response_panel.py` | Add urgency classification to actions. |
| `src/app/components/scorecard.py` | Move to landing page only; remove from investigation tabs. |
| Multiple files | Update deprecated `use_container_width=True` calls. |

---

## 7. Regression Risks

| Change | Risk | Mitigation |
|---|---|---|
| Fixing severity computation (F01) | Could break 20/20 accuracy if classification logic altered | Run `python -m pytest src/tests/test_all_events.py -v` after change. Tests assert LIKELY_LEAK classification — severity value is not strictly asserted. |
| Changing default adapter to live (F03) | Mock-specific tests still pass but no longer exercised by default | Safe — tests explicitly instantiate adapters directly. |
| Restructuring tabs (F05) | Could break confidence/scenario panel integration | Both are standalone components; work in any container. |
| Reducing pipeline map height (F04) | Station labels might overlap if too small | Test at both resolutions. |
| Removing summary alert sentence | Summary text is the only full investigation narrative | Keep accessible — move to Investigation tab body or expandable link. |
| Changing sidebar labels (F15) | Sidebar event selection depends on event_id, not label text | Safe — click handler uses event dict, not label. |

---

## 8. Implementation Sequence

### Phase A — Fix P0 blockers (30 min)

1. **Fix severity computation** (F01): Widen SCADA window in `_determine_severity` or cross-reference wider data. Verify 20/20 still pass.
2. **Change default adapter to live** (F03): In `__init__.py`, change default return.
3. **Verify:** Restart Streamlit. LK-005 → near_rupture. LK-002 → moderate. FP-001 → FALSE_POSITIVE.

### Phase B — Fix information hierarchy (1-2 hr)

4. **Shrink title** (F09): H2, shorter text.
5. **Reduce pipeline map height** (F04): 120→80px.
6. **Remove/condense summary alert** (F04).
7. **Restructure tabs** (F05): Merge to 2 tabs.
8. **Expand alternatives** (F06): Inline or expanded=True.
9. **Verify at 1280x720:** Evidence visible above fold.

### Phase C — Polish (1 hr)

10. **Fix confidence panel for FPs** (F08).
11. **Improve observation formatting** (F07).
12. **Rename sidebar sections** (F15).
13. **Fix deprecation warnings** (F16).

### Phase D — Optional enhancements

14. **SCADA context overlays** (F10).
15. **Investigation window shading** (F11).
16. **FP station highlight on map** (F13).
17. **Action urgency labels** (F12).

---

## 9. Acceptance Criteria

### P0 criteria (must pass before demo)

- [ ] LK-005 investigation shows severity `near_rupture`, not `moderate`
- [ ] LK-001 investigation shows severity `seep`, not `moderate`
- [ ] LK-003 investigation shows severity `significant`, not `moderate`
- [ ] LK-002 investigation still shows severity `moderate` (unchanged)
- [ ] Sidebar severity label and investigation severity agree for all 5 leak events
- [ ] Default `AGENT_MODE` is `live` (or all 20 events work in default mode)
- [ ] Clicking LK-005, LK-002, FP-001, and FP-003 all produce correct, non-error results
- [ ] 89/89 tests pass
- [ ] 20/20 batch scorecard accuracy

### P1 criteria (should pass before demo)

- [ ] At 1280x720, evidence section visible above fold (or within one scroll line)
- [ ] Alternative explanations visible without clicking (not collapsed)
- [ ] Tab count is 3 or fewer for leak events
- [ ] Evaluation Scorecard does not appear as investigation tab
- [ ] Confidence panel does not show wrong segment data for FP events

### P2 criteria (nice to have)

- [ ] Sidebar does not use "Confirmed Leaks"/"False Positives" as section headers
- [ ] No Streamlit deprecation warnings in logs
- [ ] SCADA chart shows at least one context overlay
- [ ] Pipeline map highlights investigated station for FP events
- [ ] Recommended actions include urgency classification

### Demo walkthrough verification

After all changes, verify these 3 demo scenarios end-to-end:

1. **LK-002 (moderate leak):** Click → LIKELY LEAK, Moderate, SEG-05, mile ~119, 94% confidence. Evidence shows sustained MBD, 3 alternatives ruled out. Actions: dispatch crew, isolate segment, monitor PHMSA. 4 citations.

2. **FP-001 (compressor start):** Click → FALSE POSITIVE, high confidence. Evidence shows compressor running, MBD near zero. Action: continue monitoring. 2 citations.

3. **LK-005 (near-rupture):** Click → LIKELY LEAK, **Near Rupture**, SEG-01, mile ~15, high confidence. Actions should include emergency isolation. This is the emergency-response story.

4. **FP-003 (temperature/line pack):** Click → FALSE POSITIVE, confidence reflects temperature correlation.
