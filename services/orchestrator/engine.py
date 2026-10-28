"""Dynamic Orchestrator Agent (`services.orchestrator.engine`).

Responsibilities:
- Maintain auditable registry of all 11 specialized agents, roles, allowed MCP tools, and budgets.
- Construct bounded multi-stage execution DAGs from approved templates per `ResearchIntent`.
- Execute independent domain agents in parallel (`ThreadPoolExecutor`) with strict timeouts and retries.
- Enforce mandatory `data_governance_agent` pre-check and `critic_agent` post-verification before
  publishing any stock research recommendation.
- Detect inter-agent signal conflicts (e.g., technical momentum vs fundamental valuation or calibrated probability).
- Persist full execution trace to `ops_agent_traces`.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, List, Optional
import uuid
from mcp.bigquery.server import bq_mcp_server
from orchestration.config import settings
from orchestration.contracts import (
    AgentExecutionResult,
    CompletionStatus,
    ResearchIntent,
)
from services.agents.specialists import SPECIALIZED_AGENT_REGISTRY


# Approved Bounded Execution Plan Templates (Stage 1: Governance Gate -> Stage 2: Parallel Research -> Stage 3: Synthesis & Critic)
INTENT_EXECUTION_PLANS: Dict[ResearchIntent, List[List[str]]] = {
    ResearchIntent.MARKET_REGIME: [
        ["data_governance_agent"],
        ["market_regime_agent", "performance_agent"],
    ],
    ResearchIntent.CATALYST_RESEARCH: [
        ["data_governance_agent"],
        ["market_data_agent", "news_catalyst_agent", "fundamental_agent"],
        ["critic_agent"],
    ],
    ResearchIntent.FORECASTING: [
        ["data_governance_agent"],
        ["quantitative_agent", "forecasting_agent", "risk_agent"],
        ["critic_agent"],
    ],
    ResearchIntent.RISK_EVALUATION: [
        ["data_governance_agent"],
        ["market_regime_agent", "risk_agent", "fundamental_agent"],
        ["critic_agent"],
    ],
    ResearchIntent.PERFORMANCE_ANALYSIS: [
        ["data_governance_agent"],
        ["performance_agent", "forecasting_agent"],
    ],
    ResearchIntent.STOCK_ANALYSIS: [
        ["data_governance_agent"],
        [
            "market_regime_agent",
            "market_data_agent",
            "news_catalyst_agent",
            "quantitative_agent",
            "forecasting_agent",
            "fundamental_agent",
            "risk_agent",
        ],
        ["critic_agent", "recommendation_agent"],
    ],
    ResearchIntent.FULL_RECOMMENDATION_WORKFLOW: [
        ["data_governance_agent"],
        [
            "market_regime_agent",
            "market_data_agent",
            "news_catalyst_agent",
            "quantitative_agent",
            "forecasting_agent",
            "fundamental_agent",
            "risk_agent",
            "performance_agent",
        ],
        ["critic_agent", "recommendation_agent"],
    ],
}


class DynamicOrchestrator:
    """Bounded Dynamic Orchestrator enforcing governance, concurrency, budgets, and critic verification."""

    def __init__(self) -> None:
        self.registry = SPECIALIZED_AGENT_REGISTRY

    def get_agent_registry_manifest(self) -> List[Dict[str, Any]]:
        """Return auditable manifest of all registered specialized agents and their allowed MCP tools."""
        manifest: List[Dict[str, Any]] = []
        for name, agent in self.registry.items():
            manifest.append(
                {
                    "agent_name": name,
                    "agent_version": agent.agent_version,
                    "role_summary": agent.role_summary,
                    "epistemic_classification": agent.epistemic_classification.value,
                    "allowed_mcp_tools": agent.allowed_tools,
                    "timeout_seconds": agent.timeout_seconds,
                    "max_token_budget": agent.max_token_budget,
                }
            )
        return manifest

    def build_execution_plan(
        self, intent: ResearchIntent, custom_agents: Optional[List[str]] = None
    ) -> List[List[str]]:
        """Construct a bounded multi-stage execution plan from approved templates."""
        if custom_agents:
            for a_name in custom_agents:
                if a_name not in self.registry:
                    raise ValueError(
                        f"Unapproved agent '{a_name}' requested. Dynamic spawning is restricted to registered templates."
                    )
            middle_stage = [
                a for a in custom_agents if a not in ("data_governance_agent", "critic_agent", "recommendation_agent")
            ]
            plan: List[List[str]] = [["data_governance_agent"]]
            if middle_stage:
                plan.append(middle_stage)
            plan.append(["critic_agent", "recommendation_agent"])
            return plan
        return INTENT_EXECUTION_PLANS.get(intent, INTENT_EXECUTION_PLANS[ResearchIntent.STOCK_ANALYSIS])

    def _run_single_agent_with_retry(
        self, agent_name: str, request_id: str, context: Dict[str, Any]
    ) -> AgentExecutionResult:
        agent = self.registry[agent_name]
        last_res: Optional[AgentExecutionResult] = None
        for attempt in range(settings.max_retries + 1):
            res = agent.execute(request_id=request_id, context=context)
            res.telemetry.retries = attempt
            if res.status != CompletionStatus.FAILED:
                return res
            last_res = res
        assert last_res is not None
        return last_res

    def _detect_conflicts(
        self, results: Dict[str, AgentExecutionResult]
    ) -> List[str]:
        """Detect divergence across quantitative, fundamental, and forecasting signals."""
        conflicts: List[str] = []
        q_res = results.get("quantitative_agent")
        f_res = results.get("forecasting_agent")
        fund_res = results.get("fundamental_agent")
        risk_res = results.get("risk_agent")

        if q_res and f_res:
            ret_20d = q_res.metrics.get("ret_20d_pct", 0.0)
            prob_5d = f_res.metrics.get("prob_up_5d", 0.5)
            if ret_20d > 5.0 and prob_5d < 0.48:
                conflicts.append(
                    f"Momentum/Model Divergence: Trailing 20d return is +{ret_20d:.1f}%, but calibrated 5d upside probability is muted ({prob_5d:.2f}), suggesting mean-reversion risk."
                )
            elif ret_20d < -5.0 and prob_5d > 0.56:
                conflicts.append(
                    f"Reversal Signal Conflict: Trailing 20d return is {ret_20d:.1f}%, while calibrated 5d model projects upside recovery ({prob_5d:.2f})."
                )

        if fund_res and f_res:
            rev_g = fund_res.metrics.get("revenue_growth_yoy_pct", 0.0)
            prob_5d = f_res.metrics.get("prob_up_5d", 0.5)
            if rev_g < 0.0 and prob_5d >= 0.55:
                conflicts.append(
                    f"Fundamental/Quant Divergence: Point-in-time YoY revenue growth is negative ({rev_g:.1f}%) despite positive short-term technical/quant signal ({prob_5d:.2f})."
                )

        if risk_res and f_res:
            vol_20d = risk_res.metrics.get("vol_20d_ann_pct", 20.0)
            if vol_20d > 38.0:
                conflicts.append(
                    f"Elevated Volatility Regime Warning: 20d annualized volatility ({vol_20d:.1f}%) widens the 90% forecast interval substantially."
                )
        return conflicts

    def execute_workflow(
        self,
        intent: ResearchIntent,
        ticker: Optional[str] = None,
        user_query: str = "",
        enable_live_vertex: bool = False,
        custom_agents: Optional[List[str]] = None,
        sync_trace_to_bq: bool = False,
    ) -> Dict[str, Any]:
        """Run the bounded multi-stage agent workflow and return validated outputs + audit trace."""
        t0 = time.perf_counter()
        request_id = f"req-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        trace_id = f"trace-{uuid.uuid4().hex[:10]}"

        context: Dict[str, Any] = {
            "ticker": (ticker or "NVDA").strip().upper(),
            "intent": intent.value,
            "user_query": user_query,
            "enable_live_vertex": enable_live_vertex,
        }

        plan = self.build_execution_plan(intent=intent, custom_agents=custom_agents)
        stage_results: Dict[str, AgentExecutionResult] = {}
        executed_order: List[str] = []

        # Stage 1: Mandatory Data Governance Gate
        gov_res = self._run_single_agent_with_retry("data_governance_agent", request_id, context)
        stage_results["data_governance_agent"] = gov_res
        executed_order.append("data_governance_agent")

        governance_verdict = gov_res.findings.get("governance_verdict", "PASS")
        blocked_by_governance = governance_verdict == "BLOCK"

        # Execute subsequent stages if not blocked by Data Governance
        if not blocked_by_governance:
            for stage_agents in plan[1:]:
                if len(stage_agents) == 1:
                    a_name = stage_agents[0]
                    stage_results[a_name] = self._run_single_agent_with_retry(
                        a_name, request_id, context
                    )
                    executed_order.append(a_name)
                else:
                    max_workers = min(len(stage_agents), settings.max_parallel_agents)
                    with ThreadPoolExecutor(max_workers=max_workers) as pool:
                        future_map = {
                            pool.submit(
                                self._run_single_agent_with_retry, a_name, request_id, context
                            ): a_name
                            for a_name in stage_agents
                        }
                        for fut, a_name in future_map.items():
                            try:
                                res = fut.result(timeout=settings.agent_timeout_seconds)
                            except FuturesTimeoutError:
                                res = self.registry[a_name].execute(request_id, context)
                                res.status = CompletionStatus.PARTIAL
                                res.warnings.append(
                                    f"Agent '{a_name}' exceeded timeout ({settings.agent_timeout_seconds}s); fallback used."
                                )
                            stage_results[a_name] = res
                            executed_order.append(a_name)

        conflicts = self._detect_conflicts(stage_results)
        critic_res = stage_results.get("critic_agent")
        critic_verdict = (
            critic_res.findings.get("critic_verdict", "APPROVED_WITH_UNCERTAINTY_BOUNDS")
            if critic_res
            else ("ABSTAIN_MANDATED" if blocked_by_governance else "NOT_INVOKED_FOR_INTENT")
        )

        # Enforce publication gate: if Data Governance blocked or Critic mandated abstention, override recommendation stance
        rec_res = stage_results.get("recommendation_agent")
        publication_allowed = (not blocked_by_governance) and (critic_verdict != "ABSTAIN_MANDATED")
        if rec_res and not publication_allowed:
            rec_res.status = CompletionStatus.ABSTAINED
            rec_res.uncertainty.abstained = True
            rec_res.uncertainty.abstention_reason = (
                f"Publication blocked by governance ({governance_verdict}) or critic ({critic_verdict})."
            )
            if "focus_recommendation" in rec_res.findings and rec_res.findings["focus_recommendation"]:
                rec_res.findings["focus_recommendation"]["research_stance"] = "ABSTAIN_INSUFFICIENT_EVIDENCE"
                rec_res.findings["focus_recommendation"]["abstained"] = True

        total_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        total_tokens = sum(
            r.telemetry.prompt_tokens + r.telemetry.completion_tokens for r in stage_results.values()
        )
        total_cost = sum(r.telemetry.estimated_cost_usd for r in stage_results.values())

        trace_row = {
            "trace_id": trace_id,
            "request_id": request_id,
            "trace_date": datetime.now(timezone.utc).date().isoformat(),
            "user_query": user_query or f"{intent.value}:{context['ticker']}",
            "intent_class": intent.value,
            "target_tickers": context["ticker"],
            "orchestrator_plan_json": json.dumps(plan),
            "agents_invoked_json": json.dumps(executed_order),
            "critic_verdict": critic_verdict,
            "governance_verdict": governance_verdict,
            "total_latency_ms": total_latency_ms,
            "total_tokens_used": int(total_tokens),
            "estimated_cost_usd": float(total_cost),
            "status": "ABSTAINED" if not publication_allowed else "COMPLETED",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        bq_mcp_server.record_agent_trace(trace_row, sync_to_bq=sync_trace_to_bq)

        return {
            "request_id": request_id,
            "trace_id": trace_id,
            "intent": intent.value,
            "ticker": context["ticker"],
            "execution_plan": plan,
            "agents_executed": executed_order,
            "governance_verdict": governance_verdict,
            "critic_verdict": critic_verdict,
            "publication_allowed": publication_allowed,
            "signal_conflicts": conflicts,
            "total_latency_ms": total_latency_ms,
            "agent_results": {k: v.model_dump() for k, v in stage_results.items()},
        }


orchestrator_engine = DynamicOrchestrator()
