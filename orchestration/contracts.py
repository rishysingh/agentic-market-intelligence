"""Common Typed Execution Contracts and Schemas for All Agents (Pydantic v2).

Every agent in the hierarchy (Root, Orchestrator, and all 11 Specialized Agents)
communicates strictly via these validated models. This contract separates:
1. Measured historical facts (with source attribution & timestamps)
2. Calibrated quantitative model forecasts (with explicit target definitions & Brier/AUC scores)
3. Agent interpretations & scenario narratives
4. Independent Critic validation & Data Governance verdicts
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CompletionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"


class DataFreshnessStatus(str, Enum):
    LIVE_INTRADAY = "LIVE_INTRADAY"
    DELAYED_EOD = "DELAYED_EOD"
    STALE = "STALE"
    MISSING = "MISSING"


class EpistemicType(str, Enum):
    MEASURED_HISTORICAL_FACT = "MEASURED_HISTORICAL_FACT"
    CALIBRATED_MODEL_FORECAST = "CALIBRATED_MODEL_FORECAST"
    AGENT_INTERPRETATION = "AGENT_INTERPRETATION"
    UNVERIFIED_HYPOTHESIS = "UNVERIFIED_HYPOTHESIS"


class ResearchIntent(str, Enum):
    MARKET_REGIME = "MARKET_REGIME"
    STOCK_ANALYSIS = "STOCK_ANALYSIS"
    CATALYST_RESEARCH = "CATALYST_RESEARCH"
    FORECASTING = "FORECASTING"
    RISK_EVALUATION = "RISK_EVALUATION"
    PERFORMANCE_ANALYSIS = "PERFORMANCE_ANALYSIS"
    FULL_RECOMMENDATION_WORKFLOW = "FULL_RECOMMENDATION_WORKFLOW"


class SourceCitation(BaseModel):
    """Verifiable provenance reference distinguishing event time from publication time."""

    source_id: str = Field(default_factory=lambda: f"src-{uuid.uuid4().hex[:8]}")
    source_type: str = Field(
        ...,
        description="SEC_EDGAR | MARKET_DATA_EOD | FRED_MACRO | GOOGLE_SEARCH_GROUNDED | BIGQUERY_WAREHOUSE",
    )
    title: str
    url: str
    event_timestamp: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp when the underlying economic/corporate event occurred.",
    )
    publication_timestamp: str = Field(
        default_factory=utc_now_iso,
        description="ISO-8601 timestamp when the data or filing became publicly available (point-in-time anchor).",
    )
    retrieval_timestamp: str = Field(default_factory=utc_now_iso)
    is_verified_filing: bool = False
    snippet: Optional[str] = None


class UncertaintySpecification(BaseModel):
    """Explicitly defined statistical uncertainty or evidence completeness metric."""

    meaning: str = Field(
        ...,
        description="Explicit definition of what this number represents (e.g., 'Out-of-sample Platt-calibrated empirical probability' vs 'Data completeness ratio'). Never subjective LLM confidence.",
    )
    epistemic_type: EpistemicType = EpistemicType.CALIBRATED_MODEL_FORECAST
    point_estimate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    lower_bound_90: Optional[float] = None
    upper_bound_90: Optional[float] = None
    calibration_method: str = "Platt-Sigmoid-WalkForward"
    brier_score: Optional[float] = None
    brier_skill_score: Optional[float] = None
    sample_size: Optional[int] = None
    abstained: bool = False
    abstention_reason: Optional[str] = None


class ValidationFinding(BaseModel):
    """Single validation or governance check outcome."""

    check_name: str
    passed: bool
    severity: str = Field(default="INFO", description="INFO | WARNING | CRITICAL")
    message: str


class ExecutionTelemetry(BaseModel):
    """Observability metadata for cost, latency, retries, and resource tracking."""

    started_at_utc: str = Field(default_factory=utc_now_iso)
    completed_at_utc: str = Field(default_factory=utc_now_iso)
    duration_ms: float = 0.0
    model_id: str = "deterministic-python"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls_count: int = 0
    retries: int = 0
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    estimated_cost_usd: float = 0.0


class AgentExecutionResult(BaseModel):
    """Universal typed contract returned by every specialized agent and orchestrator stage."""

    request_id: str
    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:10]}")
    agent_name: str
    agent_version: str = "1.0.0"
    task_description: str
    status: CompletionStatus
    as_of_utc: str = Field(default_factory=utc_now_iso)
    input_dataset_versions: Dict[str, str] = Field(default_factory=dict)
    feature_version: str = "v1.0-pit"
    epistemic_classification: EpistemicType = EpistemicType.MEASURED_HISTORICAL_FACT
    findings: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    citations: List[SourceCitation] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    uncertainty: UncertaintySpecification
    validation_results: List[ValidationFinding] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    telemetry: ExecutionTelemetry = Field(default_factory=ExecutionTelemetry)
    errors: List[str] = Field(default_factory=list)

    @field_validator("agent_name")
    @classmethod
    def validate_agent_name_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("agent_name must be non-empty")
        return v.strip()


class HorizonForecastPayload(BaseModel):
    """Explicitly defined forecast for a single trading horizon (e.g. 1d, 5d, 20d)."""

    horizon_days: int = Field(..., description="Forecast horizon in trading days (1, 5, or 20)")
    target_definition: str = Field(
        ...,
        description="Explicit statistical event definition, e.g., 'Forward 5-trading-day excess return over SPY >= +4.0%'",
    )
    target_threshold_pct: float
    calibrated_prob_up: float = Field(..., ge=0.0, le=1.0)
    calibrated_prob_down: float = Field(..., ge=0.0, le=1.0)
    expected_excess_return_bps: float
    prediction_interval_low_pct: float
    prediction_interval_high_pct: float
    signal_direction: str = Field(..., description="BULLISH | NEUTRAL | BEARISH | ABSTAIN")
    model_id: str
    model_version: str
    feature_version: str
    roc_auc_oos: float
    brier_score_oos: float
    brier_skill_score_oos: float
    abstained: bool = False
    abstention_reason: Optional[str] = None
    top_feature_drivers: List[Dict[str, Any]] = Field(default_factory=list)


class ScenarioAnalysisPayload(BaseModel):
    """Structured Bullish, Base-Case, and Bearish research scenarios with explicit invalidation triggers."""

    bullish_case: str
    bullish_target_return_pct: float
    bullish_key_drivers: List[str]
    base_case: str
    base_target_return_pct: float
    base_key_drivers: List[str]
    bearish_case: str
    bearish_target_return_pct: float
    bearish_key_drivers: List[str]
    thesis_invalidation_conditions: List[str]
    disconfirming_evidence: List[str]
