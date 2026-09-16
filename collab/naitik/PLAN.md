# Naitik — Data & Detection Logic

Tools: `query_scada`, `check_operational_context`, `locate_leak`

## 2026-09-16 — Built all 3 tools, tested against labeled events

- Created `src/tools/query_scada.py` — aggregated SCADA summary for station + time window
- Created `src/tools/check_operational_context.py` — compressor/valve/temp disambiguation
- Created `src/tools/locate_leak.py` — pressure gradient localization + valve mapping
- All 3 tested: real leaks correctly have no operational cause + sustained mass balance deficit
- False positives correctly identified (compressor starts, temp line pack)
- Localization accuracy: 0.1-8.4 mile error across 3 tested leaks
- Next: full validation against all 20 labeled events
