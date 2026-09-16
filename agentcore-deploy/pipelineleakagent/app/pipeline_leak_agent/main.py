from typing import Any
from collections import OrderedDict
from strands import Agent
import asyncio
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from tools import (
    query_scada,
    check_operational_context,
    locate_leak,
    get_segment_risk_profile,
    lookup_operating_envelope,
    get_regulatory_guidance,
)

app = BedrockAgentCoreApp()
log = app.logger

SYSTEM_PROMPT = """You are a Pipeline Leak Detection & Incident Response Agent for a 200-mile natural gas transmission pipeline with 8 SCADA stations (ST-01 through ST-08) and 7 segments (SEG-01 through SEG-07).

Your job is to analyze pipeline anomalies end-to-end: detect, classify, recommend response, and determine regulatory reporting requirements. Every claim you make MUST cite the specific data, procedure section, or regulation that supports it.

## WORKFLOW

When given an event to analyze, follow these three phases IN ORDER:

### PHASE 1: DETECTION & TRIAGE
1. Use `query_scada` to pull readings around the event time for the affected station(s)
2. Use `check_operational_context` to look for compressor starts, valve changes, or temperature drops that could explain the anomaly
3. Use `lookup_operating_envelope` to compare readings against normal ranges
4. CLASSIFY the event:
   - If a compressor start, valve change, or temperature drop explains the pressure/flow anomaly → FALSE POSITIVE. State which pattern it matches and cite Operating Procedures Section 5.1.
   - If NO operational explanation exists AND mass balance deficit is sustained >0.15 MMSCFD for >10 minutes → POTENTIAL LEAK. Cite Operating Procedures Section 3.1.

### PHASE 2: RESPONSE (only if classified as leak)
5. Use `locate_leak` to estimate the leak location from pressure gradients
6. Use `get_segment_risk_profile` to understand the segment's integrity context
7. Recommend response actions per the isolation decision tree:
   - Leak rate >0.3 MMSCFD → isolate segment (cite Operating Procedures Section 3.2)
   - Leak rate <0.3 MMSCFD → dispatch crew, reduce pressure to 700 psi max
   - Pressure drop >50 psi in <5 min → immediate ESD (cite Operating Procedures Section 4.1)
8. Name the specific isolation valves to close with their mile markers

### PHASE 3: COMPLIANCE (only if classified as leak)
9. Use `get_regulatory_guidance` to check reporting thresholds
10. Determine if NRC notification is required (49 CFR 191.5):
    - Gas loss ≥3 MMSCF
    - Property damage ≥$50,000
    - Injury, death, fire, or explosion
    - Emergency shutdown
11. If reporting will be triggered, calculate time-to-threshold and state the deadline
12. Generate a draft NRC notification using this template:
    - Operator, pipeline system, contact info (use placeholders)
    - Incident date/time, location (mile marker), coordinates (placeholder)
    - Estimated release rate, cumulative release
    - Cause (preliminary)
    - Actions taken (isolation valves closed, crew dispatched)
    - Reference: 49 CFR 191.5, PHMSA Form 7100.1

## OUTPUT FORMAT

Structure your response with clear headers:

**CLASSIFICATION**: [LEAK / FALSE POSITIVE] — one-line summary with evidence

**EVIDENCE CHAIN**: Bullet list of supporting data points with sources

**RESPONSE RECOMMENDATION**: (leaks only) Specific actions with procedure citations

**COMPLIANCE STATUS**: (leaks only) Reporting requirements with regulation citations

**DRAFT NRC NOTIFICATION**: (if reporting triggered) Pre-filled template

## RULES
- Never guess. If the data is insufficient, say so.
- Always cite the specific data source: file name, row values, or procedure section.
- Keep tool calls focused — don't dump the entire SCADA dataset.
- When comparing to thresholds, show the actual values vs. the threshold.
"""

tools = [
    query_scada,
    check_operational_context,
    locate_leak,
    get_segment_risk_profile,
    lookup_operating_envelope,
    get_regulatory_guidance,
]

_INLINE_FUNCTION_NAMES = {t.tool_name for t in tools if hasattr(t, 'tool_name')}


def _make_conversation_manager():
    return NullConversationManager()


def agent_factory():
    cache = OrderedDict()
    def get_or_create_agent(session_id):
        if session_id in cache:
            cache.move_to_end(session_id)
            return cache[session_id]
        if len(cache) >= 128:
            cache.popitem(last=False)
        cache[session_id] = Agent(
            model=load_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            conversation_manager=_make_conversation_manager(),
            hooks=[],
        )
        return cache[session_id]
    return get_or_create_agent


get_or_create_agent = agent_factory()


def strip_trailing_tool_use(messages: Any) -> list[dict]:
    """Strip toolUse blocks from the tail until the last message has none."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    messages = list(messages)
    while messages:
        last = messages[-1]
        if not isinstance(last, dict):
            raise ValueError("each message must be an object")
        original_content = last.get("content", [])
        if not isinstance(original_content, list) or not all(isinstance(block, dict) for block in original_content):
            raise ValueError("each message content value must be a list of content blocks")

        content = [block for block in original_content if "toolUse" not in block]
        if len(content) == len(original_content):
            break
        if content:
            messages[-1] = {**last, "content": content}
            break
        messages.pop()

    return messages


def _extract_prompt(payload: dict):
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "messages" in payload:
        return strip_trailing_tool_use(payload["messages"])
    if "tool_results" in payload:
        tool_results = payload["tool_results"]
        if not isinstance(tool_results, list) or not all(
            isinstance(tool_result, dict) and isinstance(tool_result.get("toolUseId"), str)
            for tool_result in tool_results
        ):
            raise ValueError("tool_results must contain objects with a toolUseId string")
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in tool_results]}]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


def _has_inline_function_call(messages) -> bool:
    """Return True if messages contains an assistant toolUse for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES or not isinstance(messages, list):
        return False
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("toolUse", {}).get("name") in _INLINE_FUNCTION_NAMES:
                    return True
    return False


def _is_inline_function_call(event: dict) -> bool:
    """Check if a contentBlockStart event is for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES:
        return False
    cbs = event.get("contentBlockStart", {})
    start = cbs.get("start", {})
    tool_use = start.get("toolUse") if isinstance(start, dict) else None
    return tool_use is not None and tool_use.get("name") in _INLINE_FUNCTION_NAMES


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Pipeline Leak Detection Agent...")

    session_id = getattr(context, 'session_id', 'default-session')
    agent = get_or_create_agent(session_id)

    prompt = _extract_prompt(payload)

    async for event in agent.stream_async(prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
