"""Tests for all 6 individual pipeline detection tools."""
import pytest

from src.tools.query_scada import query_scada
from src.tools.check_operational_context import check_operational_context
from src.tools.locate_leak import locate_leak
from src.tools.get_segment_risk_profile import get_segment_risk_profile
from src.tools.lookup_operating_envelope import lookup_operating_envelope
from src.tools.get_regulatory_guidance import get_regulatory_guidance


# --- query_scada ---

class TestQueryScada:
    def test_valid_station_returns_pressure_flow_mbd(self):
        result = query_scada("ST-05", "2026-01-04T23:45:00", "2026-01-05T00:15:00")
        assert isinstance(result, dict)
        assert "pressure" in result
        assert "flow" in result
        assert "mass_balance_deficit" in result
        assert result["station_id"] == "ST-05"
        assert result["readings_count"] > 0

    def test_pressure_has_expected_keys(self):
        result = query_scada("ST-01", "2025-12-04T07:00:00", "2025-12-04T07:30:00")
        p = result["pressure"]
        assert "start_psi" in p
        assert "end_psi" in p
        assert "min_psi" in p
        assert "max_psi" in p
        assert "drop_psi" in p

    def test_invalid_station_returns_error(self):
        result = query_scada("ST-99", "2026-01-04T23:00:00", "2026-01-05T00:00:00")
        assert "error" in result

    def test_empty_window_returns_error(self):
        result = query_scada("ST-01", "2020-01-01T00:00:00", "2020-01-01T01:00:00")
        assert "error" in result

    def test_leak_event_has_sustained_deficit(self):
        result = query_scada("ST-05", "2026-01-05T00:00:00", "2026-01-05T00:15:00")
        assert result["mass_balance_deficit"]["sustained_above_0.15"] is True

    def test_normal_period_has_no_sustained_deficit(self):
        result = query_scada("ST-01", "2025-12-01T12:00:00", "2025-12-01T13:00:00")
        assert result["mass_balance_deficit"]["sustained_above_0.15"] is False


# --- check_operational_context ---

class TestCheckOperationalContext:
    def test_real_leak_returns_context_structure(self):
        """Real leaks may still have temp signals in the lookback window;
        the key is that sustained MBD overrides operational context in the adapter."""
        result = check_operational_context("ST-05", "2026-01-05T00:00:00")
        assert "has_operational_cause" in result
        assert result["compressor"]["start_detected"] is False

    def test_compressor_start_detected(self):
        result = check_operational_context("ST-01", "2025-12-04T07:00:00")
        assert result["has_operational_cause"] is True
        assert result["compressor"]["start_detected"] is True

    def test_temperature_line_pack_detected(self):
        result = check_operational_context("ST-02", "2025-12-11T05:00:00")
        assert result["has_operational_cause"] is True
        assert result["temperature"]["line_pack_effect"] is True

    def test_returns_expected_structure(self):
        result = check_operational_context("ST-03", "2026-01-01T12:00:00")
        assert "station_id" in result
        assert "compressor" in result
        assert "valve" in result
        assert "temperature" in result
        assert "explanations" in result


# --- locate_leak ---

class TestLocateLeak:
    def test_lk002_returns_seg05(self):
        result = locate_leak("ST-05", "2026-01-05T00:00:00")
        assert isinstance(result, dict)
        assert result.get("segment_id") == "SEG-05"

    def test_lk002_mile_marker_within_range(self):
        result = locate_leak("ST-05", "2026-01-05T00:00:00")
        mile = result.get("estimated_mile_marker", 0)
        assert 104 <= mile <= 130, f"Mile marker {mile} outside SEG-05 range"

    def test_returns_isolation_valves(self):
        result = locate_leak("ST-05", "2026-01-05T00:00:00")
        assert "recommended_isolation" in result
        assert "upstream_valve" in result["recommended_isolation"]
        assert "downstream_valve" in result["recommended_isolation"]

    def test_invalid_station_returns_error(self):
        result = locate_leak("ST-99", "2026-01-05T00:00:00")
        assert "error" in result

    def test_lk005_returns_seg01(self):
        result = locate_leak("ST-01", "2026-02-24T00:00:00")
        assert result.get("segment_id") == "SEG-01"


# --- get_segment_risk_profile ---

class TestGetSegmentRiskProfile:
    def test_seg05_returns_inspection_data(self):
        result = get_segment_risk_profile("SEG-05")
        assert isinstance(result, str)
        assert "SEG-05" in result
        assert "INSPECTIONS" in result
        assert "CP:" in result

    def test_normalizes_bare_segment_id(self):
        result = get_segment_risk_profile("05")
        assert "SEG-05" in result

    def test_invalid_segment_returns_message(self):
        result = get_segment_risk_profile("SEG-99")
        assert "No segment found" in result

    def test_seg01_returns_encroachment_data(self):
        result = get_segment_risk_profile("SEG-01")
        assert "ENCROACHMENTS" in result


# --- lookup_operating_envelope ---

class TestLookupOperatingEnvelope:
    def test_st05_returns_pressure_range(self):
        result = lookup_operating_envelope("ST-05")
        assert isinstance(result, str)
        assert "ST-05" in result
        assert "pressure" in result.lower()
        assert "flow" in result.lower()

    def test_returns_transient_signatures(self):
        result = lookup_operating_envelope("ST-01")
        assert "compressor_start" in result
        assert "valve_change" in result
        assert "temperature_line_pack" in result

    def test_returns_isolation_decision_tree(self):
        result = lookup_operating_envelope("ST-03")
        assert "ISOLATION" in result
        assert "0.3 MMSCFD" in result

    def test_invalid_station_returns_error(self):
        result = lookup_operating_envelope("ST-99")
        assert "Unknown station" in result


# --- get_regulatory_guidance ---

class TestGetRegulatoryGuidance:
    def test_moderate_leak_shows_time_to_threshold(self):
        result = get_regulatory_guidance(0.52, 0)
        assert "TIME TO THRESHOLD" in result
        assert "5." in result  # ~5.8 days

    def test_zero_rate_returns_inf(self):
        result = get_regulatory_guidance(0.0, 0)
        assert "inf" in result.lower() or "Not yet required" in result

    def test_injury_triggers_immediate_reporting(self):
        result = get_regulatory_guidance(0.1, 0, has_injury=True)
        assert "Injury" in result
        assert "immediate" in result.lower() or "NRC" in result

    def test_fire_triggers_immediate_reporting(self):
        result = get_regulatory_guidance(0.1, 0, has_fire=True)
        assert "Fire" in result

    def test_threshold_exceeded_triggers_reporting(self):
        result = get_regulatory_guidance(1.0, 100)
        assert "EXCEEDS" in result

    def test_below_threshold_shows_monitoring(self):
        result = get_regulatory_guidance(0.1, 0)
        assert "Not yet required" in result or "Monitor" in result
