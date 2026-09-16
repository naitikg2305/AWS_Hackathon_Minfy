"""Pipeline Leak Detection Agent — entry point.

Usage:
    python -m src.main                          # interactive mode
    python -m src.main "Analyze event LK-002"   # single prompt
"""
import sys

from src.agents.pipeline_agent import create_agent

EXAMPLE_PROMPTS = {
    "LK-001": "Analyze event LK-001: seep detected near mile 47.2 on SEG-02, onset 2025-12-12T23:48:00, estimated leak rate 0.18 MMSCFD. Classify, recommend response, and check compliance.",
    "LK-002": "Analyze event LK-002: moderate leak detected near mile 119.3 on SEG-05, onset 2026-01-04T23:55:00, estimated leak rate 0.52 MMSCFD. Classify, recommend response, and check compliance.",
    "LK-003": "Analyze event LK-003: significant leak detected near mile 72.0 on SEG-03, onset 2026-01-27T23:55:00, estimated leak rate 1.1 MMSCFD. Classify, recommend response, and check compliance.",
    "LK-004": "Analyze event LK-004: moderate leak detected near mile 182.1 on SEG-07, onset 2026-02-10T23:51:00, estimated leak rate 0.35 MMSCFD. Classify, recommend response, and check compliance.",
    "LK-005": "Analyze event LK-005: near-rupture detected near mile 13.6 on SEG-01, onset 2026-02-23T23:49:00, estimated leak rate 2.4 MMSCFD. Classify, recommend response, and check compliance.",
    "FP-001": "Analyze event FP-001: pressure anomaly at ST-01, timestamp 2025-12-04T14:00:00, pressure drop 13.8 psi lasting 19 minutes. Is this a real leak or false positive?",
    "FP-003": "Analyze event FP-003: pressure anomaly at ST-02, timestamp 2025-12-11T05:00:00, pressure drop 17.5 psi lasting 11 minutes. Is this a real leak or false positive?",
}


def main():
    agent = create_agent()

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        if prompt in EXAMPLE_PROMPTS:
            prompt = EXAMPLE_PROMPTS[prompt]
        result = agent(prompt)
        print("\n" + "=" * 60)
        print("AGENT RESPONSE:")
        print("=" * 60)
        return

    print("Pipeline Leak Detection & Incident Response Agent")
    print("=" * 50)
    print("Example events: LK-001 through LK-005 (leaks), FP-001/FP-003 (false positives)")
    print("Type an event ID or a free-form question. Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        if user_input in EXAMPLE_PROMPTS:
            user_input = EXAMPLE_PROMPTS[user_input]

        result = agent(user_input)
        print()


if __name__ == "__main__":
    main()
