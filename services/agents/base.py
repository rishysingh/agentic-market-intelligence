"""Base Specialized Agent Class & ADK Integration Helper (`services.agents.base`)."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from mcp.security import AGENT_TOOL_ALLOWLIST
from orchestration.contracts import (
    AgentExecutionResult,
    CompletionStatus,
    EpistemicType,
    ExecutionTelemetry,
    SourceCitation,
    UncertaintySpecification,
    ValidationFinding,
)


class BaseSpecializedAgent(ABC):
    """Abstract base class for all 11 specialized domain agents."""

    agent_name: str = "base_agent"
    agent_version: str = "1.0.0"
    role_summary: str = "Base specialized agent"
    epistemic_classification: EpistemicType = EpistemicType.MEASURED_HISTORICAL_FACT
    timeout_seconds: float = 12.0
    max_token_budget: int = 2048

    @property
    def allowed_tools(self) -> List[str]:
        return sorted(AGENT_TOOL_ALLOWLIST.get(self.agent_name, set()))

    def execute(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        """Execute the agent's task within bounded telemetry and return a validated `AgentExecutionResult`."""
        t0 = time.perf_counter()
        started_iso = datetime.now(timezone.utc).isoformat()
        try:
            result = self._run_impl(request_id=request_id, context=context)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            result.telemetry.started_at_utc = started_iso
            result.telemetry.completed_at_utc = datetime.now(timezone.utc).isoformat()
            result.telemetry.duration_ms = elapsed_ms
            return result
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return AgentExecutionResult(
                request_id=request_id,
                agent_name=self.agent_name,
                agent_version=self.agent_version,
                task_description=self.role_summary,
                status=CompletionStatus.FAILED,
                epistemic_classification=self.epistemic_classification,
                findings={"error_detail": str(exc)},
                uncertainty=UncertaintySpecification(
                    meaning="Agent execution failed; abstention required.",
                    epistemic_type=self.epistemic_classification,
                    abstained=True,
                    abstention_reason=str(exc),
                ),
                errors=[str(exc)],
                telemetry=ExecutionTelemetry(
                    started_at_utc=started_iso,
                    completed_at_utc=datetime.now(timezone.utc).isoformat(),
                    duration_ms=elapsed_ms,
                    fallback_triggered=True,
                    fallback_reason=str(exc),
                ),
            )

    @abstractmethod
    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        """Domain-specific implementation returning `AgentExecutionResult`."""
        raise NotImplementedError
