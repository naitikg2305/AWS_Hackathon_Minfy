from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Classification(str, Enum):
    LIKELY_LEAK = "LIKELY_LEAK"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    INCONCLUSIVE = "INCONCLUSIVE"


class Severity(str, Enum):
    SEEP = "seep"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    NEAR_RUPTURE = "near_rupture"


class Status(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    ERROR = "error"
    TIMEOUT = "timeout"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EstimatedLocation(BaseModel):
    mile_marker: float
    uncertainty_miles: float


class Observation(BaseModel):
    label: str
    value: str
    station_id: str
    timestamp: str


class AlternativeConsidered(BaseModel):
    cause: str
    result: str = Field(description="ruled_out, unlikely, or possible")
    reason: str


class IntegrityContext(BaseModel):
    ili_risk: Optional[str] = None
    cp_status: Optional[str] = None
    nearby_encroachment: Optional[bool] = None


class RecommendedAction(BaseModel):
    priority: int
    action: str
    basis: str


class Citation(BaseModel):
    source: str
    locator: str
    claim: str


class InvestigationResult(BaseModel):
    event_id: str
    status: Status
    classification: Classification
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Optional[Severity] = None
    affected_segment: Optional[str] = None
    estimated_location: Optional[EstimatedLocation] = None
    summary: str
    observations: list[Observation] = Field(default_factory=list)
    alternatives_considered: list[AlternativeConsidered] = Field(default_factory=list)
    integrity_context: Optional[IntegrityContext] = None
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    trace_id: Optional[str] = None
