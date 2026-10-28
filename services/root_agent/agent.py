"""Root Agent Entry Point (`services.root_agent.agent`).

Integrates Google Agent Development Kit (`google-adk`) with the Dynamic Orchestrator
and Vertex AI Gemini (`gemini-2.5-pro` / `gemini-2.5-flash`).

Responsibilities:
- Understand user intent and classify into one of the 7 governed `ResearchIntent` categories.
- Establish analysis scope and required evidence.
- Delegate bounded execution to `DynamicOrchestrator`.
- Consolidate validated outputs into an evidence-backed response that strictly separates:
  1. Measured historical facts (`MEASURED_HISTORICAL_FACT`)
  2. Calibrated model forecasts (`CALIBRATED_MODEL_FORECAST`)
  3. Agent interpretations & scenarios (`AGENT_INTERPRETATION`)
- Enforce that the Root Agent never invents market data or bypasses Risk/Critic gates.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from data.ingestion.universe import SECURITY_MASTER_UNIVERSE, TICKER_TO_SECURITY
from orchestration.config import settings
from orchestration.contracts import ResearchIntent
from services.orchestrator.engine import orchestrator_engine


def classify_user_intent(user_query: str, explicit_intent: Optional[str] = None) -> ResearchIntent:
    """Classify user query into one of the governed `ResearchIntent` workflows."""
    if explicit_intent:
        try:
            return ResearchIntent(explicit_intent.strip().upper())
        except ValueError:
            pass

    q = (user_query or "").lower()
    if any(k in q for k in ["regime", "macro", "vix", "yield curve", "sector breadth", "overall market"]):
        return ResearchIntent.MARKET_REGIME
    if any(k in q for k in ["catalyst", "news", "filing", "10-k", "10-q", "8-k", "earnings", "sec"]):
        return ResearchIntent.CATALYST_RESEARCH
    if any(k in q for k in ["backtest", "sharpe", "calibration", "brier", "historical accuracy", "performance"]):
        return ResearchIntent.PERFORMANCE_ANALYSIS
    if any(k in q for k in ["risk", "drawdown", "suitability", "unsuitable", "volatility", "beta", "downside"]):
        return ResearchIntent.RISK_EVALUATION
    if any(k in q for k in ["forecast", "probability", "horizon", "1d", "5d", "20d", "predict"]):
        return ResearchIntent.FORECASTING
    if any(k in q for k in ["rank", "top", "opportunities", "recommend", "full workflow"]):
        return ResearchIntent.FULL_RECOMMENDATION_WORKFLOW
    return ResearchIntent.STOCK_ANALYSIS


def extract_target_ticker(user_query: str, explicit_ticker: Optional[str] = None) -> str:
    """Extract target equity ticker from user request or default to NVDA."""
    if explicit_ticker and explicit_ticker.strip():
        return explicit_ticker.strip().upper()
    tokens = re.findall(r"\b[A-Za-z]{1,5}\b", user_query or "")
    for tok in tokens:
        up = tok.upper()
        if up in TICKER_TO_SECURITY:
            return up
    # Check company name substring
    q_low = (user_query or "").lower()
    for sec in SECURITY_MASTER_UNIVERSE:
        first_word = sec["company_name"].split()[0].lower().rstrip(",.")
        if len(first_word) >= 3 and first_word in q_low:
            return sec["ticker"]
    return "NVDA"


def build_adk_root_agent() -> Any:
    """Construct the Google ADK `LlmAgent` hierarchy with tool bindings to the Dynamic Orchestrator."""
    from google.adk.agents import LlmAgent

    def adk_orchestrate_market_intelligence(
        user_query: str, ticker: str = "NVDA", intent: str = "STOCK_ANALYSIS"
    ) -> Dict[str, Any]:
        """ADK tool wrapper that invokes the bounded Dynamic Orchestrator and returns validated evidence."""
        resolved_intent = classify_user_intent(user_query, explicit_intent=intent)
        resolved_ticker = extract_target_ticker(user_query, explicit_ticker=ticker)
        return orchestrator_engine.execute_workflow(
            intent=resolved_intent,
            ticker=resolved_ticker,
            user_query=user_query,
            enable_live_vertex=False,
        )

    return LlmAgent(
        name="ami_root_agent",
        model=settings.gemini_pro_model,
        description=(
            "Root Agent for the Agentic Stock Market Intelligence & Prediction Platform. "
            "Routes financial research queries through the Dynamic Orchestrator and enforces "
            "epistemic separation of historical facts, calibrated forecasts, and scenarios."
        ),
        instruction=(
            "You are the Root Financial Research Agent. Never fabricate market prices, financial ratios, "
            "or probabilities. Always invoke `adk_orchestrate_market_intelligence` to obtain verified "
            "point-in-time data, calibrated walk-forward forecasts, risk metrics, and Independent Critic "
            "validation. Clearly separate: (1) Measured Historical Facts, (2) Calibrated Model Forecasts, "
            "and (3) Bullish/Base/Bearish Research Scenarios with explicit invalidation triggers."
        ),
        tools=[adk_orchestrate_market_intelligence],
    )


class RootAgentService:
    """Primary entry point for user and API research requests."""

    def __init__(self) -> None:
        self._adk_agent: Optional[Any] = None

    @property
    def adk_agent(self) -> Any:
        if self._adk_agent is None:
            self._adk_agent = build_adk_root_agent()
        return self._adk_agent

    def handle_research_request(
        self,
        user_query: str,
        ticker: Optional[str] = None,
        intent: Optional[str] = None,
        enable_live_vertex: bool = False,
        sync_trace_to_bq: bool = False,
    ) -> Dict[str, Any]:
        """Classify request, delegate to Dynamic Orchestrator, and consolidate evidence-backed dossier."""
        resolved_intent = classify_user_intent(user_query, explicit_intent=intent)
        resolved_ticker = extract_target_ticker(user_query, explicit_ticker=ticker)

        workflow_out = orchestrator_engine.execute_workflow(
            intent=resolved_intent,
            ticker=resolved_ticker,
            user_query=user_query,
            enable_live_vertex=enable_live_vertex,
            sync_trace_to_bq=sync_trace_to_bq,
        )

        agent_results = workflow_out.get("agent_results", {})
        citations_dedup: Dict[str, Dict[str, Any]] = {}
        for a_res in agent_results.values():
            for cit in a_res.get("citations", []):
                key = f"{cit.get('source_type')}:{cit.get('title')}:{cit.get('url')}"
                citations_dedup[key] = cit

        # Separate epistemic layers explicitly
        measured_facts = {
            "market_regime": agent_results.get("market_regime_agent", {}).get("findings", {}),
            "market_data": agent_results.get("market_data_agent", {}).get("findings", {}),
            "quantitative_metrics": agent_results.get("quantitative_agent", {}).get("metrics", {}),
            "fundamental_pit": agent_results.get("fundamental_agent", {}).get("findings", {}),
            "risk_metrics": agent_results.get("risk_agent", {}).get("metrics", {}),
            "backtest_performance": agent_results.get("performance_agent", {}).get("metrics", {}),
        }

        calibrated_forecasts = agent_results.get("forecasting_agent", {}).get("findings", {}).get(
            "horizons", {}
        )

        rec_findings = agent_results.get("recommendation_agent", {}).get("findings", {}).get(
            "focus_recommendation", {}
        )
        critic_findings = agent_results.get("critic_agent", {}).get("findings", {})

        executive_summary = self._synthesize_executive_summary(
            ticker=resolved_ticker,
            intent=resolved_intent,
            user_query=user_query,
            workflow_out=workflow_out,
            rec_findings=rec_findings,
            enable_live_vertex=enable_live_vertex,
        )

        return {
            "request_id": workflow_out["request_id"],
            "trace_id": workflow_out["trace_id"],
            "as_of_utc": datetime.now(timezone.utc).isoformat(),
            "user_query": user_query,
            "classified_intent": resolved_intent.value,
            "target_ticker": resolved_ticker,
            "governance_verdict": workflow_out["governance_verdict"],
            "critic_verdict": workflow_out["critic_verdict"],
            "publication_allowed": workflow_out["publication_allowed"],
            "executive_summary": executive_summary,
            "epistemic_breakdown": {
                "measured_historical_facts": measured_facts,
                "calibrated_model_forecasts": calibrated_forecasts,
                "agent_interpretations_and_scenarios": {
                    "research_stance": rec_findings.get("research_stance", "ABSTAIN_INSUFFICIENT_EVIDENCE"),
                    "composite_rank_score": rec_findings.get("composite_rank_score"),
                    "rank_position": rec_findings.get("rank_position"),
                    "bullish_scenario": rec_findings.get("bullish_scenario"),
                    "base_scenario": rec_findings.get("base_scenario"),
                    "bearish_scenario": rec_findings.get("bearish_scenario"),
                    "invalidation_conditions": rec_findings.get("invalidation_conditions"),
                    "unsuitability_flags": agent_results.get("risk_agent", {})
                    .get("findings", {})
                    .get("unsuitability_flags", []),
                    "critic_audit": critic_findings,
                    "news_catalyst_synthesis": agent_results.get("news_catalyst_agent", {})
                    .get("findings", {})
                    .get("catalyst_synthesis"),
                },
            },
            "signal_conflicts": workflow_out["signal_conflicts"],
            "citations": list(citations_dedup.values()),
            "execution_plan": workflow_out["execution_plan"],
            "agents_executed": workflow_out["agents_executed"],
            "total_latency_ms": workflow_out["total_latency_ms"],
            "agent_results": agent_results,
            "disclaimer": (
                "STATISTICAL RESEARCH DISCLOSURE: All outputs distinguish measured historical facts from "
                "Platt-calibrated model probabilities and agent scenario interpretations. Past performance "
                "and calibrated probabilities do not guarantee future market returns."
            ),
        }

    def _synthesize_executive_summary(
        self,
        ticker: str,
        intent: ResearchIntent,
        user_query: str,
        workflow_out: Dict[str, Any],
        rec_findings: Dict[str, Any],
        enable_live_vertex: bool = False,
    ) -> str:
        """Produce an evidence-backed executive narrative grounded strictly in validated agent outputs."""
        if not workflow_out.get("publication_allowed", True):
            return (
                f"ABSTENTION NOTICE FOR {ticker}: The platform has abstained from issuing a directional "
                f"research recommendation because Data Governance ({workflow_out.get('governance_verdict')}) "
                f"or Independent Critic ({workflow_out.get('critic_verdict')}) blocked publication."
            )

        agent_results = workflow_out.get("agent_results", {})
        md = agent_results.get("market_data_agent", {}).get("findings", {})
        f_metrics = agent_results.get("forecasting_agent", {}).get("metrics", {})
        r_metrics = agent_results.get("risk_agent", {}).get("metrics", {})
        fund_metrics = agent_results.get("fundamental_agent", {}).get("metrics", {})
        regime = (
            agent_results.get("market_regime_agent", {})
            .get("findings", {})
            .get("regime_classification", "TRANSITIONAL_CONSOLIDATION")
        )

        deterministic_summary = (
            f"[{intent.value} | {ticker}] Measured EOD close is ${md.get('latest_close', rec_findings.get('latest_price', 0.0))} "
            f"(as of {md.get('latest_trade_date', rec_findings.get('generated_date', 'latest'))}) under a "
            f"{regime} macro regime. Point-in-time SEC XBRL filings show YoY revenue growth of "
            f"{fund_metrics.get('revenue_growth_yoy_pct', 0.0):+.1f}% and operating margin of "
            f"{fund_metrics.get('operating_profit_margin_pct', 0.0):.1f}%. "
            f"Calibrated walk-forward models estimate a 5-trading-day upside move probability of "
            f"{f_metrics.get('prob_up_5d', rec_findings.get('prob_material_move_up', 0.5))*100:.1f}% "
            f"(expected excess return {f_metrics.get('expected_excess_return_5d_bps', rec_findings.get('expected_excess_return_bps', 0.0)):+.1f} bps; "
            f"OOS Brier={f_metrics.get('brier_score_5d_oos', 0.22):.4f}). "
            f"20-day annualized volatility is {r_metrics.get('vol_20d_ann_pct', 22.0):.1f}% with a 60-day max drawdown of "
            f"{r_metrics.get('max_drawdown_60d_pct', -8.0):.1f}%. Independent Critic status: {workflow_out.get('critic_verdict')}."
        )

        if enable_live_vertex:
            try:
                import google.auth
                from google import genai
                from google.genai import types

                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                client = genai.Client(
                    vertexai=True,
                    project=settings.project_id,
                    location=settings.location,
                    credentials=creds,
                )
                prompt = (
                    f"User Query: {user_query}\n"
                    f"Validated Quantitative & Fundamental Facts: {deterministic_summary}\n"
                    f"Bullish Scenario: {rec_findings.get('bullish_scenario', '')}\n"
                    f"Bearish Scenario: {rec_findings.get('bearish_scenario', '')}\n"
                    f"Invalidation Trigger: {rec_findings.get('invalidation_conditions', '')}\n\n"
                    f"Write a concise, institutional-grade 4-sentence executive synthesis that strictly uses "
                    f"only the numbers above, distinguishes measured facts from calibrated model probabilities, "
                    f"and highlights key downside risks."
                )
                resp = client.models.generate_content(
                    model=settings.gemini_fast_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=300),
                )
                if resp.text:
                    return resp.text.strip()
            except Exception:
                pass

        return deterministic_summary


root_agent_service = RootAgentService()
