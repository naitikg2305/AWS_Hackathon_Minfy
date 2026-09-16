# Team Sync Log

All team members: append your updates here after every push so everyone sees the full picture.

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
