"""MCP server entrypoint: exposes the validated leak-detection agent as MCP tools.

Runs on AgentCore Runtime with protocol MCP (streamable HTTP, stateless, 0.0.0.0:8000/mcp).
Any MCP client with access can call it: Amazon Quick (after the authorizer is switched to CUSTOM_JWT,
see docs/quick-mcp-integration.md), Strands/LangChain agents, Claude Code, or the AWS CLI via
invoke-agent-runtime with a JSON-RPC body.

Design: ONE tool wraps the whole agent (prompt + 6 tools) so the 20/20 validated behavior is what every
client gets, rather than letting the client's model re-derive the leak call from the raw tools.
"""
from pathlib import Path

import pandas as pd
from mcp.server.fastmcp import FastMCP
from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager

from model.load import load_model
from prompt import SYSTEM_PROMPT
from tools import (
    query_scada,
    check_operational_context,
    locate_leak,
    get_segment_risk_profile,
    lookup_operating_envelope,
    get_regulatory_guidance,
)

DATA_DIR = Path(__file__).resolve().parent / "data"

# stateless_http=True is required on AgentCore Runtime; the service routes to 0.0.0.0:8000/mcp.
mcp = FastMCP("pipeline-leak-agent", host="0.0.0.0", port=8000, stateless_http=True)

AGENT_TOOLS = [
    query_scada,
    check_operational_context,
    locate_leak,
    get_segment_risk_profile,
    lookup_operating_envelope,
    get_regulatory_guidance,
]


@mcp.tool()
def investigate_pipeline_event(
    station_id: str,
    start_time: str,
    end_time: str,
    event_id: str = "",
) -> str:
    """Investigate a natural-gas pipeline pressure/flow anomaly and decide whether it is a real LEAK or a
    FALSE POSITIVE (compressor start, valve change, or cold-weather line-pack shrink).

    Use this when someone asks "was that pressure drop at station X a leak?", "is there a leak on the
    pipeline right now?", or "what should we do about the alarm at ST-03?". It pulls SCADA readings, weather,
    valve and compressor logs, inspection and cathodic-protection history, and PHMSA/49 CFR rules, then
    returns a cited verdict: CLASSIFICATION, SEVERITY, evidence chain, isolation valves to close, whether
    NRC/PHMSA reporting is required, and a draft NRC notification. Takes about 20-40 seconds.

    Args:
        station_id: SCADA station, ST-01 through ST-08 (e.g. "ST-03").
        start_time: ISO-8601 start of the window to analyze, e.g. "2026-01-27T23:40:00".
        end_time: ISO-8601 end of the window, e.g. "2026-01-28T00:25:00".
        event_id: Optional alarm/event label such as "LK-003" or "FP-001" for the report header.
    """
    agent = Agent(
        model=load_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=AGENT_TOOLS,
        conversation_manager=NullConversationManager(),
        callback_handler=None,
    )
    prompt = (
        f"Analyze event {event_id or 'UNLABELED'}: pressure anomaly detected at station {station_id} "
        f"between {start_time} and {end_time}. Is this a real leak or a false positive? "
        f"Follow the full 3-phase workflow."
    )
    return str(agent(prompt))


@mcp.tool()
def list_alarm_events(kind: str = "all") -> str:
    """List the pipeline alarm events available to investigate, with station, time window and type.

    Use this first when the user does not know a station ID or time, e.g. "what alarms happened in
    January?" or "show me the leak events". Returns one line per event: event_id, station, start, end, and
    the labeled type (leak severity or false-positive cause). Pass kind="leak" or kind="false_positive" to
    filter, or "all" for everything.
    """
    rows = []
    if kind in ("all", "leak"):
        leaks = pd.read_csv(DATA_DIR / "labeled_leak_events.csv")
        meta = pd.read_csv(DATA_DIR / "pipeline_segment_metadata.csv").set_index("segment_id")
        for _, r in leaks.iterrows():
            ts = pd.Timestamp(r["onset_timestamp"])
            station = meta.loc[r["affected_segment"], "from_station"] if r["affected_segment"] in meta.index else "ST-01"
            rows.append(
                f"{r['event_id']} | {station} | {(ts - pd.Timedelta(minutes=15)).isoformat()} | "
                f"{(ts + pd.Timedelta(minutes=30)).isoformat()} | leak ({r['severity']}, {r['leak_rate_mmscfd']} MMSCFD, mile {r['true_leak_location_mile_marker']})"
            )
    if kind in ("all", "false_positive"):
        fps = pd.read_csv(DATA_DIR / "labeled_false_positive_events.csv")
        for _, r in fps.iterrows():
            ts = pd.Timestamp(r["timestamp"])
            rows.append(
                f"{r['event_id']} | {r['station_id']} | {(ts - pd.Timedelta(hours=1)).isoformat()} | "
                f"{(ts + pd.Timedelta(minutes=30)).isoformat()} | false_positive ({r['fp_type']})"
            )
    header = "event_id | station | window_start | window_end | labeled_type"
    return "\n".join([header] + rows) if rows else "No events found. kind must be all, leak, or false_positive."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
