"""Run labeled events through the DEPLOYED AgentCore agent via the UI adapter and score them.

This is the check the hackathon never ran: the 20/20 validation covered the Python tools
(AGENT_MODE=live), not the LLM agent. Usage (from repo root, needs AWS creds for minfy-rnd):

    AWS_PROFILE=minfy-rnd .venv/bin/python src/tests/eval_agentcore_events.py            # all 20
    AWS_PROFILE=minfy-rnd .venv/bin/python src/tests/eval_agentcore_events.py LK-005 FP-001

Events run in parallel (default 4 at a time). Each live run is ~20-60 s and costs Bedrock tokens.
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("AGENT_MODE", "agentcore")

from src.app.adapters.agentcore_agent import AgentCoreAdapter  # noqa: E402
from src.app.components.alarm_queue import _load_all_events  # noqa: E402
from src.app.models.investigation import Classification  # noqa: E402


def main(argv: list[str]) -> int:
    wanted = set(argv)
    events = [e for e in _load_all_events() if not wanted or e["event_id"] in wanted]
    adapter = AgentCoreAdapter()
    workers = int(os.environ.get("EVAL_WORKERS", "4"))

    def run(ev):
        t = time.time()
        r = adapter.investigate_event(ev["event_id"], ev["station_id"], ev["start_timestamp"], ev["end_timestamp"])
        return ev, r, time.time() - t

    rows, correct = [], 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for ev, r, secs in pool.map(run, events):
            expected = Classification.LIKELY_LEAK if ev["type"] == "leak" else Classification.FALSE_POSITIVE
            ok = r.classification == expected
            correct += ok
            sev = r.severity.value if r.severity else "-"
            rows.append((ev["event_id"], expected.value, r.classification.value, sev, ev.get("severity") or ev.get("fp_type", ""), f"{secs:.0f}s", "OK" if ok else "WRONG"))
            print(f"{ev['event_id']:7} expected={expected.value:15} got={r.classification.value:15} sev={sev:13} truth={rows[-1][4]:22} {secs:4.0f}s {'OK' if ok else 'WRONG'}", flush=True)

    print(f"\n{correct}/{len(events)} correct")
    return 0 if correct == len(events) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
