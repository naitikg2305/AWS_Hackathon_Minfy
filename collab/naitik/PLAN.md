# Naitik — Data & Detection Logic

Tools: `query_scada`, `check_operational_context`, `locate_leak`

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
