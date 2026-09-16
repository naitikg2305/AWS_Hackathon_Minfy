"""Adapter that invokes the deployed AgentCore agent and parses its response."""
import json
import os
import re
import time

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

RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:260287467863:"
    "runtime/pipelineleakagent_pipeline_leak_agent-9djKrBCyoX"
)


class AgentCoreAdapter(AgentAdapter):
    def __init__(self):
        self.runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN", RUNTIME_ARN)
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-agentcore", region_name=self.region)

    def investigate_event(
        self,
        event_id: str,
        station_id: str,
        start_timestamp: str,
        end_timestamp: str,
    ) -> InvestigationResult:
        try:
            return self._invoke_and_parse(event_id, station_id, start_timestamp, end_timestamp)
        except Exception as e:
            return InvestigationResult(
                event_id=event_id,
                status=Status.ERROR,
                classification=Classification.INCONCLUSIVE,
                confidence=0.0,
                summary=f"AgentCore invocation failed: {str(e)}",
            )

    def _invoke_and_parse(
        self, event_id: str, station_id: str, start_timestamp: str, end_timestamp: str
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

        body = response["response"].read().decode("utf-8")
        text = self._extract_text_from_sse(body)
        trace_id = f"agentcore-{event_id}-{int(time.time())}"

        return self._parse_agent_response(event_id, station_id, start_timestamp, end_timestamp, text, trace_id)

    def _extract_text_from_sse(self, body: str) -> str:
        text_parts = []
        for line in body.split("\n"):
            line = line.strip()
            if not line.startswith("data: "):
                continue
            try:
                data = json.loads(line[6:])
                event = data.get("event", {})
                delta = event.get("contentBlockDelta", {}).get("delta", {})
                if "text" in delta:
                    text_parts.append(delta["text"])
            except json.JSONDecodeError:
                continue
        return "".join(text_parts)

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

        if "FALSE POSITIVE" in text_upper:
            classification = Classification.FALSE_POSITIVE
        elif "LIKELY LEAK" in text_upper or "POTENTIAL LEAK" in text_upper or "**CLASSIFICATION**: LEAK" in text.upper():
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
            if "NEAR.?RUPTURE" in text_upper or "IMMEDIATE ESD" in text_upper:
                severity = Severity.NEAR_RUPTURE
            elif "SIGNIFICANT" in text_upper:
                severity = Severity.SIGNIFICANT
            elif "MODERATE" in text_upper:
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
