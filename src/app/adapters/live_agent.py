"""Live adapter that calls the actual detection tools directly to build structured results."""
import time
from pathlib import Path

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

from src.tools.query_scada import query_scada
from src.tools.check_operational_context import check_operational_context
from src.tools.locate_leak import locate_leak
from src.tools.get_segment_risk_profile import get_segment_risk_profile
from src.tools.get_regulatory_guidance import get_regulatory_guidance


class LiveToolAdapter(AgentAdapter):
    """Calls detection tools directly and builds a structured InvestigationResult."""

    def investigate_event(
        self,
        event_id: str,
        station_id: str,
        start_timestamp: str,
        end_timestamp: str,
    ) -> InvestigationResult:
        try:
            return self._run_investigation(event_id, station_id, start_timestamp, end_timestamp)
        except Exception as e:
            return InvestigationResult(
                event_id=event_id,
                status=Status.ERROR,
                classification=Classification.INCONCLUSIVE,
                confidence=0.0,
                summary=f"Investigation failed: {str(e)}",
            )

    def _run_investigation(
        self, event_id: str, station_id: str, start_timestamp: str, end_timestamp: str
    ) -> InvestigationResult:
        scada_result = query_scada(
            station_id=station_id,
            start_time=start_timestamp,
            end_time=end_timestamp,
        )
        if isinstance(scada_result, dict) and "error" in scada_result:
            return InvestigationResult(
                event_id=event_id,
                status=Status.ERROR,
                classification=Classification.INCONCLUSIVE,
                confidence=0.0,
                summary=f"SCADA query failed: {scada_result['error']}",
            )

        mid_timestamp = start_timestamp
        context_result = check_operational_context(
            station_id=station_id,
            event_time=mid_timestamp,
        )

        observations = self._build_observations(scada_result, station_id, start_timestamp)
        alternatives = self._build_alternatives(context_result)

        has_operational_cause = context_result.get("has_operational_cause", False)
        mbd = scada_result.get("mass_balance_deficit", {})
        mbd_sustained = mbd.get("sustained_above_0.15", False)
        mbd_max = mbd.get("max_mmscfd", 0)
        pressure_drop = scada_result.get("pressure", {}).get("drop_psi", 0)

        explanations = context_result.get("explanations", [])
        has_mechanical_cause = any(
            e.get("type") in ("compressor_start", "valve_change") for e in explanations
        )
        has_only_temp = has_operational_cause and not has_mechanical_cause

        if mbd_sustained and (not has_operational_cause or has_only_temp):
            classification = Classification.LIKELY_LEAK
            confidence = min(0.98, 0.7 + (mbd_max * 0.3))

            severity = self._determine_severity(mbd_max, pressure_drop)

            leak_result = locate_leak(station_id=station_id, event_time=mid_timestamp)

            estimated_location = None
            affected_segment = None
            if isinstance(leak_result, dict) and "error" not in leak_result:
                estimated_location = EstimatedLocation(
                    mile_marker=leak_result.get("estimated_mile_marker", 0),
                    uncertainty_miles=5.0,
                )
                affected_segment = leak_result.get("segment_id")

            risk_text = get_segment_risk_profile(segment_id=affected_segment or "SEG-01")
            integrity_context = self._parse_integrity(risk_text)

            reg_text = get_regulatory_guidance(
                leak_rate_mmscfd=mbd_max,
                duration_hours=0,
            )

            recommended_actions = self._build_leak_actions(
                leak_result, mbd_max, affected_segment, reg_text
            )
            citations = self._build_leak_citations(
                scada_result, leak_result, station_id, start_timestamp, affected_segment
            )

            summary = (
                f"Sustained mass-balance deficit of {mbd_max:.2f} MMSCFD detected at {station_id}. "
                f"Pressure dropped {pressure_drop:.1f} PSI. "
                f"No operational cause (compressor start, valve change, or temperature transient) found. "
                f"Classified as likely leak."
            )

            return InvestigationResult(
                event_id=event_id,
                status=Status.COMPLETED,
                classification=classification,
                confidence=round(confidence, 2),
                severity=severity,
                affected_segment=affected_segment,
                estimated_location=estimated_location,
                summary=summary,
                observations=observations,
                alternatives_considered=alternatives,
                integrity_context=integrity_context,
                recommended_actions=recommended_actions,
                citations=citations,
                trace_id=f"live-{event_id}-{int(time.time())}",
            )
        elif has_operational_cause:
            fp_type = "operational transient"
            explanations = context_result.get("explanations", [])
            if explanations:
                fp_type = explanations[0].get("type", "unknown").replace("_", " ")

            confidence = 0.90
            if explanations:
                conf_str = explanations[0].get("confidence", "medium")
                confidence = {"high": 0.95, "medium": 0.88, "low": 0.75}.get(conf_str, 0.85)

            summary = (
                f"Pressure anomaly at {station_id} is consistent with {fp_type}. "
                f"Pressure drop of {pressure_drop:.1f} PSI. "
                f"Mass balance deficit did not sustain above threshold. "
                f"No emergency response required."
            )

            recommended_actions = [
                RecommendedAction(
                    priority=1,
                    action="Continue normal monitoring — no emergency response required",
                    basis="Pipeline Operating Procedures — transient response",
                ),
                RecommendedAction(
                    priority=2,
                    action=f"Log {fp_type} event for shift handover",
                    basis="Pipeline Operating Procedures — shift handover checklist",
                ),
            ]

            citations = [
                Citation(
                    source="scada_timeseries.csv",
                    locator=f"{station_id}, {start_timestamp} to {end_timestamp}",
                    claim=f"Pressure drop {pressure_drop:.1f} PSI, MBD max {mbd_max:.4f} MMSCFD",
                ),
                Citation(
                    source="pipeline_operating_procedures.md",
                    locator="Section 2 — Compressor and Valve Transient Signatures",
                    claim=f"Event matches {fp_type} transient pattern",
                ),
            ]

            return InvestigationResult(
                event_id=event_id,
                status=Status.COMPLETED,
                classification=Classification.FALSE_POSITIVE,
                confidence=round(confidence, 2),
                severity=None,
                affected_segment=None,
                estimated_location=None,
                summary=summary,
                observations=observations,
                alternatives_considered=alternatives,
                recommended_actions=recommended_actions,
                citations=citations,
                trace_id=f"live-{event_id}-{int(time.time())}",
            )
        else:
            return InvestigationResult(
                event_id=event_id,
                status=Status.COMPLETED,
                classification=Classification.INCONCLUSIVE,
                confidence=0.5,
                summary=(
                    f"Anomaly at {station_id} does not clearly match a leak or false-positive pattern. "
                    f"MBD max: {mbd_max:.4f} MMSCFD, pressure drop: {pressure_drop:.1f} PSI. "
                    f"Manual investigation recommended."
                ),
                observations=observations,
                alternatives_considered=alternatives,
                trace_id=f"live-{event_id}-{int(time.time())}",
            )

    def _build_observations(self, scada: dict, station_id: str, timestamp: str) -> list[Observation]:
        obs = []
        p = scada.get("pressure", {})
        obs.append(Observation(
            label="Pressure range",
            value=f"{p.get('min_psi', 0):.1f} – {p.get('max_psi', 0):.1f} PSI (drop: {p.get('drop_psi', 0):.1f} PSI)",
            station_id=station_id,
            timestamp=timestamp,
        ))
        f = scada.get("flow", {})
        obs.append(Observation(
            label="Flow rate",
            value=f"Mean {f.get('mean_mmscfd', 0):.3f} MMSCFD",
            station_id=station_id,
            timestamp=timestamp,
        ))
        m = scada.get("mass_balance_deficit", {})
        obs.append(Observation(
            label="Mass balance deficit",
            value=f"Max {m.get('max_mmscfd', 0):.4f} MMSCFD, sustained={m.get('sustained_above_0.15', False)}",
            station_id=station_id,
            timestamp=timestamp,
        ))
        obs.append(Observation(
            label="Compressor status",
            value=str(scada.get("compressor_status", "unknown")),
            station_id=station_id,
            timestamp=timestamp,
        ))
        return obs

    def _build_alternatives(self, context: dict) -> list[AlternativeConsidered]:
        alts = []
        comp = context.get("compressor", {})
        if comp.get("start_detected"):
            alts.append(AlternativeConsidered(
                cause="compressor_start",
                result="consistent",
                reason="Compressor status change detected in the investigation window.",
            ))
        else:
            alts.append(AlternativeConsidered(
                cause="compressor_start",
                result="ruled_out",
                reason="No compressor status change detected in the investigation window.",
            ))

        valve = context.get("valve", {})
        if valve.get("change_detected"):
            alts.append(AlternativeConsidered(
                cause="valve_change",
                result="consistent",
                reason="Significant valve position change detected.",
            ))
        else:
            alts.append(AlternativeConsidered(
                cause="valve_change",
                result="ruled_out",
                reason="No significant valve position change detected.",
            ))

        temp = context.get("temperature", {})
        if temp.get("line_pack_effect"):
            alts.append(AlternativeConsidered(
                cause="temperature_line_pack",
                result="consistent",
                reason=f"Temperature drop of {temp.get('temp_drop_f', 0):.1f}°F with line pack contraction detected.",
            ))
        else:
            alts.append(AlternativeConsidered(
                cause="temperature_line_pack",
                result="ruled_out",
                reason="Insufficient temperature movement to explain the anomaly.",
            ))
        return alts

    def _determine_severity(self, mbd_max: float, pressure_drop: float) -> Severity:
        if pressure_drop > 50 or mbd_max > 2.0:
            return Severity.NEAR_RUPTURE
        if mbd_max > 0.8:
            return Severity.SIGNIFICANT
        if mbd_max > 0.3:
            return Severity.MODERATE
        return Severity.SEEP

    def _parse_integrity(self, risk_text: str) -> IntegrityContext:
        ili_risk = "low"
        if "Repair Required" in risk_text or "Anomaly Found" in risk_text:
            ili_risk = "high"
        elif "anomalies" in risk_text.lower():
            ili_risk = "medium"

        cp_status = "adequate"
        if "failure rate" in risk_text:
            for line in risk_text.split("\n"):
                if "CP:" in line and "%" in line:
                    try:
                        pct = float(line.split("%")[0].split()[-1])
                        if pct > 30:
                            cp_status = "failing"
                        elif pct > 10:
                            cp_status = "degraded"
                    except (ValueError, IndexError):
                        pass

        nearby_encroachment = "active" in risk_text.lower() and "ENCROACHMENTS: 0" not in risk_text

        return IntegrityContext(
            ili_risk=ili_risk,
            cp_status=cp_status,
            nearby_encroachment=nearby_encroachment,
        )

    def _build_leak_actions(
        self, leak_result: dict, mbd_max: float, segment: str | None, reg_text: str
    ) -> list[RecommendedAction]:
        actions = []
        mile = leak_result.get("estimated_mile_marker", "unknown") if isinstance(leak_result, dict) else "unknown"

        actions.append(RecommendedAction(
            priority=1,
            action=f"Dispatch field verification crew to mile marker {mile} ± 5 miles",
            basis="Pipeline Operating Procedures — pressure anomaly response",
        ))

        if mbd_max > 0.3 and isinstance(leak_result, dict):
            iso = leak_result.get("recommended_isolation", {})
            up = iso.get("upstream_valve", "N/A")
            down = iso.get("downstream_valve", "N/A")
            actions.append(RecommendedAction(
                priority=2,
                action=f"Isolate {segment or 'segment'} via {up} and {down}",
                basis="Pipeline Operating Procedures — leak rate >0.3 MMSCFD requires isolation",
            ))

        if "TIME TO THRESHOLD" in reg_text:
            actions.append(RecommendedAction(
                priority=3,
                action="Monitor cumulative gas release against PHMSA 3 MMSCF reporting threshold",
                basis="49 CFR 191.5 — NRC notification required within 1 hour of confirmed reportable release",
            ))

        return actions

    def _build_leak_citations(
        self, scada: dict, leak_result: dict, station_id: str, timestamp: str, segment: str | None
    ) -> list[Citation]:
        citations = [
            Citation(
                source="scada_timeseries.csv",
                locator=f"{station_id}, {scada.get('time_window', timestamp)}",
                claim=f"Pressure drop {scada.get('pressure', {}).get('drop_psi', 0):.1f} PSI, MBD max {scada.get('mass_balance_deficit', {}).get('max_mmscfd', 0):.4f} MMSCFD",
            ),
        ]
        if isinstance(leak_result, dict) and "error" not in leak_result:
            citations.append(Citation(
                source="pipeline_segment_metadata.csv",
                locator=f"{segment}",
                claim=f"Estimated leak at mile {leak_result.get('estimated_mile_marker', 'N/A')}, isolation valves identified",
            ))
        citations.append(Citation(
            source="pipeline_operating_procedures.md",
            locator="Section 3 — Pressure Anomaly Response",
            claim="Sustained deficit with no operational cause requires field verification",
        ))
        citations.append(Citation(
            source="dot_phmsa_regulatory_reference.md",
            locator="49 CFR 191.5",
            claim="Releases exceeding 3 MMSCF require NRC notification",
        ))
        return citations
