from src.tools.query_scada import query_scada
from src.tools.check_operational_context import check_operational_context
from src.tools.locate_leak import locate_leak
from src.tools.get_segment_risk_profile import get_segment_risk_profile
from src.tools.lookup_operating_envelope import lookup_operating_envelope
from src.tools.get_regulatory_guidance import get_regulatory_guidance
from src.tools.compute_confidence import compute_confidence
from src.tools.simulate_scenario import simulate_scenario

ALL_TOOLS = [
    query_scada,
    check_operational_context,
    locate_leak,
    get_segment_risk_profile,
    lookup_operating_envelope,
    get_regulatory_guidance,
    compute_confidence,
    simulate_scenario,
]
