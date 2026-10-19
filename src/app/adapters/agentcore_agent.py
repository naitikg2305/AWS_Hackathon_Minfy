"""Adapter that invokes the deployed AgentCore agent and parses its response."""
import json
import os
import re
import time
from pathlib import Path

import boto3

from src.app.adapters.base import AgentAdapter
from src.app.models.investigation import (
    InvestigationResult,
    Classification,
    Severity,
    Status,
    EstimatedLocation,
    Observation,
    AlternativeConsidered,
    IntegrityContext,
    RecommendedAction,
    Citation,
)

# Deployed state written by `agentcore deploy` (gitignored; contains the account ID).
_DEPLOYED_STATE = (
    Path(__file__).resolve().parents[3]
    / "agentcore-deploy" / "pipelineleakagent" / "agentcore" / ".cli" / "deployed-state.json"
)


def resolve_runtime_arn() -> str:
    """AGENTCORE_RUNTIME_ARN env var, else the CLI's deployed-state.json, else a clear error."""
    arn = os.environ.get("AGENTCORE_RUNTIME_ARN")
    if arn:
        return arn
    if _DEPLOYED_STATE.exists():
        state = json.loads(_DEPLOYED_STATE.read_text())
        for target in state.get("targets", {}).values():
            runtimes = target.get("resources", {}).get("runtimes", {})
            for rt in runtimes.values():
                if rt.get("runtimeArn"):
                    return rt["runtimeArn"]
    raise RuntimeError(
        "No AgentCore runtime ARN found. Set AGENTCORE_RUNTIME_ARN or run `agentcore deploy` "
        "(see docs/deploy-agentcore.md)."
    )


class AgentCoreAdapter(AgentAdapter):
    def __init__(self):
        self.runtime_arn = resolve_runtime_arn()
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-agentcore", region_name=self.region)

    def investigate_event(
        self,
        event_id: str,
        station_id: str,
        start_timestamp: str,
        end_timestamp: str,
        on_delta=None,
    ) -> InvestigationResult:
        """Run the agent. If on_delta is given it is called with each text chunk as it streams in."""
        try:
            return self._invoke_and_parse(event_id, station_id, start_timestamp, end_timestamp, on_delta)
        except Exception as e:
            return InvestigationResult(
                event_id=event_id,
                status=Status.ERROR,
                classification=Classification.INCONCLUSIVE,
                confidence=0.0,
                summary=f"AgentCore invocation failed: {str(e)}",
            )

    def _invoke_and_parse(
        self, event_id: str, station_id: str, start_timestamp: str, end_timestamp: str, on_delta=None
    ) -> InvestigationResult:
        prompt = (
            f"Analyze event {event_id}: pressure anomaly detected at station {station_id} "
            f"between {start_timestamp} and {end_timestamp}. "
            f"Is this a real leak or a false positive? Follow the full 3-phase workflow."
        )

        response = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.runtime_arn,
            contentType="application/json",
            accept="application/json",
            payload=json.dumps({"prompt": prompt}).encode("utf-8"),
        )

        # Consume the SSE stream incrementally so the UI can show the agent's reasoning as it arrives.
        text_parts = []
        for raw in response["response"].iter_lines():
            delta = self._delta_from_sse_line(raw.decode("utf-8", errors="replace"))
            if delta:
                text_parts.append(delta)
                if on_delta is not None:
                    on_delta(delta)
        text = "".join(text_parts)
        trace_id = f"agentcore-{event_id}-{int(time.time())}"

        return self._parse_agent_response(event_id, station_id, start_timestamp, end_timestamp, text, trace_id)

    @staticmethod
    def _delta_from_sse_line(line: str) -> str:
        line = line.strip()
        if not line.startswith("data: "):
            return ""
        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError:
            return ""
        delta = data.get("event", {}).get("contentBlockDelta", {}).get("delta", {})
        return delta.get("text", "") if isinstance(delta, dict) else ""

    def _extract_text_from_sse(self, body: str) -> str:
        return "".join(self._delta_from_sse_line(line) for line in body.split("\n"))

    def _parse_agent_response(
        self,
        event_id: str,
        station_id: str,
        start_timestamp: str,
        end_timestamp: str,
        text: str,
        trace_id: str,
    ) -> InvestigationResult:
        text_upper = text.upper()

        # 1) Preferred: the explicit verdict line the system prompt asks for
        #    ("CLASSIFICATION: LEAK" / "CLASSIFICATION: FALSE POSITIVE"), tolerant of markdown decoration.
        verdict_match = re.search(
            r"CLASSIFICATION\**\s*[:\-–—]\s*\**\s*\[?\s*(FALSE\s+POSITIVE|POTENTIAL\s+LEAK|LIKELY\s+LEAK|LEAK)",
            text_upper,
        )
        if verdict_match:
            verdict = verdict_match.group(1)
            classification = (
                Classification.FALSE_POSITIVE if verdict.startswith("FALSE") else Classification.LIKELY_LEAK
            )
        # 2) Fallback for free-form answers: look for a verdict phrase, not a bare substring
        #    ("not a false positive" must not count as FALSE POSITIVE).
        elif re.search(r"(?<!NOT A )(?<!NOT )FALSE POSITIVE", text_upper) and not re.search(
            r"(LIKELY|POTENTIAL|CONFIRMED)\s+LEAK", text_upper
        ):
            classification = Classification.FALSE_POSITIVE
        elif re.search(r"(LIKELY|POTENTIAL|CONFIRMED)\s+LEAK", text_upper):
            classification = Classification.LIKELY_LEAK
        else:
            classification = Classification.INCONCLUSIVE

        confidence = 0.85
        if classification == Classification.LIKELY_LEAK:
            confidence = 0.92
        elif classification == Classification.FALSE_POSITIVE:
            confidence = 0.90

        severity = None
        if classification == Classification.LIKELY_LEAK:
            sev_match = re.search(r"SEVERITY\**\s*[:\-–—]\s*\**\s*(NEAR[\s_\-]?RUPTURE|SIGNIFICANT|MODERATE|SEEP)", text_upper)
            sev_word = sev_match.group(1) if sev_match else ""
            if sev_word.startswith("NEAR") or (not sev_match and re.search(r"NEAR[\s_\-]?RUPTURE|IMMEDIATE ESD", text_upper)):
                severity = Severity.NEAR_RUPTURE
            elif sev_word == "SIGNIFICANT" or (not sev_match and "SIGNIFICANT" in text_upper):
                severity = Severity.SIGNIFICANT
            elif sev_word == "MODERATE" or (not sev_match and "MODERATE" in text_upper):
                severity = Severity.MODERATE
            else:
                severity = Severity.SEEP

        estimated_location = None
        affected_segment = None
        mile_match = re.search(r"mile\s+(?:marker\s+)?(\d+\.?\d*)", text, re.IGNORECASE)
        seg_match = re.search(r"(SEG-\d+)", text)
        if mile_match and classification == Classification.LIKELY_LEAK:
            estimated_location = EstimatedLocation(
                mile_marker=float(mile_match.group(1)),
                uncertainty_miles=5.0,
            )
        if seg_match:
            affected_segment = seg_match.group(1)

        observations = [
            Observation(
                label="Agent analysis",
                value=text[:300] + ("..." if len(text) > 300 else ""),
                station_id=station_id,
                timestamp=start_timestamp,
            ),
        ]

        pressure_match = re.search(r"[Pp]ressure\s+drop[:\s]+(\d+\.?\d*)\s*(?:psi|PSI)", text)
        if pressure_match:
            observations.append(Observation(
                label="Pressure drop",
                value=f"{pressure_match.group(1)} PSI",
                station_id=station_id,
                timestamp=start_timestamp,
            ))

        mbd_match = re.search(r"[Mm]ass\s+balance\s+deficit[:\s]+.*?(\d+\.?\d*)\s*MMSCFD", text)
        if mbd_match:
            observations.append(Observation(
                label="Mass balance deficit",
                value=f"{mbd_match.group(1)} MMSCFD",
                station_id=station_id,
                timestamp=start_timestamp,
            ))

        alternatives = []
        for cause in ["compressor_start", "valve_change", "temperature_line_pack"]:
            cause_label = cause.replace("_", " ")
            if cause_label in text.lower() or cause in text.lower():
                if "no " + cause_label in text.lower() or "ruled out" in text.lower():
                    alternatives.append(AlternativeConsidered(
                        cause=cause, result="ruled_out", reason=f"Agent ruled out {cause_label}",
                    ))
                else:
                    alternatives.append(AlternativeConsidered(
                        cause=cause, result="consistent", reason=f"Agent found {cause_label} evidence",
                    ))

        recommended_actions = []
        if classification == Classification.LIKELY_LEAK:
            recommended_actions.append(RecommendedAction(
                priority=1,
                action="Dispatch field verification crew",
                basis="Pipeline Operating Procedures Section 3.1",
            ))
            if severity in (Severity.SIGNIFICANT, Severity.NEAR_RUPTURE):
                recommended_actions.append(RecommendedAction(
                    priority=2,
                    action="Isolate affected segment",
                    basis="Pipeline Operating Procedures Section 3.2",
                ))
        else:
            recommended_actions.append(RecommendedAction(
                priority=1,
                action="Continue normal monitoring",
                basis="Pipeline Operating Procedures Section 5.1",
            ))

        citations = [
            Citation(
                source="scada_timeseries.csv",
                locator=f"{station_id}, {start_timestamp} to {end_timestamp}",
                claim="SCADA readings analyzed by AgentCore agent",
            ),
        ]
        if "49 CFR" in text:
            citations.append(Citation(
                source="dot_phmsa_regulatory_reference.md",
                locator="49 CFR 191.5",
                claim="Regulatory compliance assessed",
            ))

        return InvestigationResult(
            event_id=event_id,
            status=Status.COMPLETED,
            classification=classification,
            confidence=confidence,
            severity=severity,
            affected_segment=affected_segment,
            estimated_location=estimated_location,
            summary=text[:500],
            observations=observations,
            alternatives_considered=alternatives,
            recommended_actions=recommended_actions,
            citations=citations,
            trace_id=trace_id,
        )
