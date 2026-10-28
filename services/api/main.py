"""Tier 2 Backend REST API & Agent Execution Layer (`services.api.main`).

Exposes documented, authenticated endpoints for:
- `/api/v1/health` (System health, data freshness SLA, DQ report, agent registry & traces)
- `/api/v1/market/overview` (Market regime, FRED macro indicators, ETF benchmarks, signal anomalies)
- `/api/v1/opportunities` (Ranked stock opportunities with transparent composite score breakdown)
- `/api/v1/stocks/{ticker}` (Full point-in-time stock research dossier, 1d/5d/20d forecasts, OHLCV, SEC filings)
- `/api/v1/performance/backtests` (Walk-forward backtest runs, equity curves, calibration reliability curves)
- `/api/v1/agent/research` (Root Agent -> Dynamic Orchestrator -> 11 Specialized Agents execution)
- `/api/v1/pipeline/refresh` (Token-protected operational refresh trigger)
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from data.ingestion.universe import SECURITY_MASTER_UNIVERSE, TICKER_TO_SECURITY
from mcp.bigquery.server import bq_mcp_server
from mcp.market_data.server import market_data_mcp_server
from mcp.research.server import research_mcp_server
from orchestration.config import settings
from services.orchestrator.engine import orchestrator_engine
from services.root_agent.agent import root_agent_service


app = FastAPI(
    title="Agentic Stock Market Intelligence & Prediction Platform API",
    description=(
        "Tier 2 Intelligence, Quantitative Forecasting, and Hierarchical Multi-Agent Orchestration API "
        "powered by Google Agent Development Kit (ADK), Vertex AI Gemini, and BigQuery."
    ),
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def verify_write_auth(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Enforce API token authentication on privileged/operational endpoints."""
    expected = settings.api_auth_token
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    token = (x_api_key or bearer or "").strip()
    if token != expected:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: valid X-API-Key or Bearer token required for operational endpoints.",
        )


class AgentResearchRequest(BaseModel):
    """Request payload for interactive Root Agent & Orchestrator research."""

    user_query: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="Natural language research query or hypothesis to investigate.",
    )
    ticker: Optional[str] = Field(
        default=None,
        description="Optional focus ticker symbol (e.g., NVDA, AAPL, MSFT, JPM).",
    )
    intent: Optional[str] = Field(
        default=None,
        description="Optional explicit ResearchIntent override.",
    )
    enable_live_vertex: bool = Field(
        default=False,
        description="Whether to invoke live Vertex AI Gemini Google Search grounding in addition to verified BigQuery/EDGAR data.",
    )


@app.get("/api/v1/health")
def get_system_health() -> Dict[str, Any]:
    """Return system health, pipeline freshness SLA, DQ report, and agent registry."""
    health_data = bq_mcp_server.get_pipeline_and_dq_health(caller_agent="root_agent")
    return {
        "status": "HEALTHY",
        "service": "ami-backend",
        "version": "1.2.0",
        "project_id": settings.project_id,
        "region": settings.location,
        "bq_dataset": f"{settings.project_id}.{settings.bq_dataset_id}",
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline_run": health_data.get("ops_pipeline_run", {}),
        "data_quality": health_data.get("dq_report", {}),
        "agent_registry": orchestrator_engine.get_agent_registry_manifest(),
        "recent_agent_traces": health_data.get("recent_agent_traces", []),
    }


@app.get("/api/v1/market/overview")
def get_market_overview() -> Dict[str, Any]:
    """Return overall market regime classification, macro indicators, sector ETFs, and top signal anomalies."""
    regime_res = orchestrator_engine.registry["market_regime_agent"].execute(
        request_id="api-market-overview", context={}
    )
    rec_bundle = bq_mcp_server.get_latest_recommendations(
        caller_agent="orchestrator_agent", limit=20
    )
    snap = bq_mcp_server._load_snapshot()
    latest_feats = [
        f for f in snap.get("latest_features", [])
        if not TICKER_TO_SECURITY.get(f.get("ticker", ""), {}).get("is_etf", False)
    ]

    # Identify top unusual volume, volatility, and momentum signals
    vol_anomalies = sorted(
        latest_feats, key=lambda x: abs(float(x.get("volume_zscore_20d", 0.0))), reverse=True
    )[:5]
    momentum_leaders = sorted(
        latest_feats, key=lambda x: float(x.get("ret_20d", 0.0)), reverse=True
    )[:5]
    high_vol_movers = sorted(
        latest_feats, key=lambda x: float(x.get("vol_20d_ann", 0.0)), reverse=True
    )[:5]

    return {
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "generated_at": snap.get("generated_at"),
        "data_freshness": snap.get("dq_report", {}).get("verdict", "PASS"),
        "latest_trade_date": snap.get("dq_report", {}).get("latest_trade_date"),
        "market_regime": regime_res.findings,
        "regime_metrics": regime_res.metrics,
        "regime_uncertainty": regime_res.uncertainty.model_dump(),
        "top_opportunities": rec_bundle.get("recommendations", [])[:6],
        "signal_monitors": {
            "volume_anomalies": [
                {
                    "ticker": f["ticker"],
                    "close_price": round(float(f["close_price"]), 2),
                    "volume_zscore_20d": round(float(f["volume_zscore_20d"]), 2),
                    "ret_1d_pct": round(float(f["ret_1d"]) * 100.0, 2),
                }
                for f in vol_anomalies
            ],
            "momentum_leaders": [
                {
                    "ticker": f["ticker"],
                    "close_price": round(float(f["close_price"]), 2),
                    "ret_20d_pct": round(float(f["ret_20d"]) * 100.0, 2),
                    "rel_strength_sector_20d_pct": round(float(f["rel_strength_sector_20d"]) * 100.0, 2),
                }
                for f in momentum_leaders
            ],
            "volatility_Alerts": [
                {
                    "ticker": f["ticker"],
                    "close_price": round(float(f["close_price"]), 2),
                    "vol_20d_ann_pct": round(float(f["vol_20d_ann"]) * 100.0, 2),
                    "max_drawdown_60d_pct": round(float(f["max_drawdown_60d"]) * 100.0, 2),
                }
                for f in high_vol_movers
            ],
        },
    }


@app.get("/api/v1/opportunities")
def list_opportunities(
    limit: int = Query(default=20, ge=1, le=50),
    sector: Optional[str] = Query(default=None),
    stance: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """List ranked stock opportunities with parsed score breakdowns, scenarios, and citations."""
    bundle = bq_mcp_server.get_latest_recommendations(
        caller_agent="orchestrator_agent", limit=50, sector=sector, stance=stance
    )
    recs = bundle.get("recommendations", [])
    if search and search.strip():
        q = search.strip().lower()
        recs = [
            r for r in recs
            if q in r.get("ticker", "").lower()
            or q in r.get("company_name", "").lower()
            or q in r.get("sector", "").lower()
        ]

    enriched: List[Dict[str, Any]] = []
    for r in recs[:limit]:
        item = dict(r)
        item["score_breakdown"] = json.loads(r.get("score_breakdown_json", "{}"))
        item["unsuitability_flags"] = json.loads(r.get("unsuitability_flags_json", "[]"))
        item["citations"] = json.loads(r.get("citations_json", "[]"))
        enriched.append(item)

    sectors = sorted({s["sector"] for s in SECURITY_MASTER_UNIVERSE if not s["is_etf"]})
    return {
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(enriched),
        "available_sectors": sectors,
        "scoring_methodology": (
            "40% Calibrated Walk-Forward Model Edge (5d/20d) + 20% Momentum & Relative Strength "
            "+ 20% Point-in-Time SEC XBRL Fundamental Quality + 20% Volatility/Drawdown Risk Penalty"
        ),
        "opportunities": enriched,
    }


@app.get("/api/v1/stocks/{ticker}")
def get_stock_research_dossier(ticker: str) -> Dict[str, Any]:
    """Return comprehensive single-stock research dossier with OHLCV, features, 1d/5d/20d forecasts, scenarios, and filings."""
    t_clean = ticker.strip().upper()
    uni = market_data_mcp_server.validate_ticker_universe(
        caller_agent="root_agent", ticker=t_clean
    )
    if not uni.get("in_universe"):
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Ticker '{t_clean}' is not in the governed Security Master universe.",
                "supported_tickers": uni.get("supported_tickers", []),
            },
        )

    sec_meta = market_data_mcp_server.get_security_metadata(
        caller_agent="market_data_agent", ticker=t_clean
    )["security"]
    ohlcv = market_data_mcp_server.get_ohlcv_history(
        caller_agent="market_data_agent", ticker=t_clean, limit_days=90
    )
    ff_bundle = bq_mcp_server.get_security_features_and_forecasts(
        caller_agent="quantitative_agent", ticker=t_clean
    )
    sec_edgar = research_mcp_server.get_sec_edgar_catalysts_and_fundamentals(
        caller_agent="fundamental_agent", ticker=t_clean
    )

    rec = ff_bundle.get("recommendation") or {}
    rec_enriched = dict(rec)
    if rec_enriched:
        rec_enriched["score_breakdown"] = json.loads(rec.get("score_breakdown_json", "{}"))
        rec_enriched["unsuitability_flags"] = json.loads(rec.get("unsuitability_flags_json", "[]"))
        rec_enriched["citations"] = json.loads(rec.get("citations_json", "[]"))

    forecasts_parsed: List[Dict[str, Any]] = []
    for p in ff_bundle.get("forecasts", []):
        p_copy = dict(p)
        p_copy["top_features"] = json.loads(p.get("top_features_json", "[]"))
        forecasts_parsed.append(p_copy)

    return {
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "ticker": t_clean,
        "security": sec_meta,
        "price_history": {
            "source_provider": ohlcv.get("source_provider"),
            "latency_class": ohlcv.get("latency_class"),
            "latest_trade_date": ohlcv.get("latest_trade_date"),
            "latest_close": ohlcv.get("latest_close"),
            "bars": ohlcv.get("bars", []),
        },
        "latest_quant_features": ff_bundle.get("latest_features", {}),
        "forecasts_by_horizon": forecasts_parsed,
        "recommendation_and_scenarios": rec_enriched,
        "sec_edgar_catalysts": sec_edgar.get("catalysts", []),
        "fundamentals_point_in_time": sec_edgar.get("fundamentals_pit", []),
        "epistemic_notice": {
            "measured_historical_facts": "price_history, latest_quant_features, fundamentals_point_in_time, sec_edgar_catalysts",
            "calibrated_model_forecasts": "forecasts_by_horizon (Platt-calibrated walk-forward probabilities)",
            "agent_interpretations": "recommendation_and_scenarios (Bullish, Base-Case, Bearish scenarios & Critic audit)",
        },
    }


@app.get("/api/v1/performance/backtests")
def get_performance_and_backtests(
    horizon_days: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    """Return walk-forward backtest runs (net of 10bps cost + 5bps slippage) and model calibration diagnostics."""
    bt_bundle = bq_mcp_server.get_backtest_metrics(
        caller_agent="performance_agent", horizon_days=horizon_days
    )
    reg_bundle = bq_mcp_server.get_model_registry_metrics(caller_agent="performance_agent")

    parsed_bts: List[Dict[str, Any]] = []
    for b in bt_bundle.get("backtests", []):
        b_copy = dict(b)
        b_copy["equity_curve"] = json.loads(b.get("equity_curve_json", "[]"))
        parsed_bts.append(b_copy)

    parsed_models: List[Dict[str, Any]] = []
    for m in reg_bundle.get("models", []):
        m_copy = dict(m)
        m_copy["hyperparameters"] = json.loads(m.get("hyperparameters_json", "{}"))
        m_copy["metrics_detail"] = json.loads(m.get("metrics_json", "{}"))
        parsed_models.append(m_copy)

    return {
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "split_design": "Expanding-window chronological walk-forward with h-trading-day embargo gap",
            "transaction_cost_bps": 10.0,
            "slippage_bps": 5.0,
            "benchmark": "SPY (SPDR S&P 500 ETF Trust)",
            "survivorship_bias_disclosure": (
                "Evaluated across the 20-equity liquid large-cap universe with strict point-in-time SEC filing timestamps."
            ),
        },
        "backtest_runs": parsed_bts,
        "model_registry": parsed_models,
    }


@app.post("/api/v1/agent/research")
def execute_agent_research(payload: AgentResearchRequest) -> Dict[str, Any]:
    """Invoke the Root Agent -> Dynamic Orchestrator -> Specialized Agents hierarchy on a user research query."""
    return root_agent_service.handle_research_request(
        user_query=payload.user_query,
        ticker=payload.ticker,
        intent=payload.intent,
        enable_live_vertex=payload.enable_live_vertex,
        sync_trace_to_bq=False,
    )


@app.post("/api/v1/pipeline/refresh", dependencies=[Depends(verify_write_auth)])
def trigger_pipeline_refresh(mode: str = Query(default="incremental")) -> Dict[str, Any]:
    """Protected operational endpoint to run an incremental or full data & model refresh."""
    from data.ingestion.pipeline import execute_pipeline

    result = execute_pipeline(mode=mode, upload_to_bq=False)
    return {
        "status": "REFRESH_COMPLETED",
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline_summary": result,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("services.api.main:app", host="0.0.0.0", port=port, reload=False)
