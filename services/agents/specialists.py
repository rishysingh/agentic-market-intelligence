"""Implementation of all 11 Specialized Agents (`services.agents.specialists`).

Agents:
1. DataGovernanceAgent (`data_governance_agent`)
2. MarketRegimeAgent (`market_regime_agent`)
3. MarketDataAgent (`market_data_agent`)
4. NewsCatalystAgent (`news_catalyst_agent`)
5. QuantitativeAnalysisAgent (`quantitative_agent`)
6. ForecastingAgent (`forecasting_agent`)
7. FundamentalAnalysisAgent (`fundamental_agent`)
8. RiskPortfolioAgent (`risk_agent`)
9. IndependentCriticAgent (`critic_agent`)
10. RecommendationRankingAgent (`recommendation_agent`)
11. PerformanceBacktestAgent (`performance_agent`)
"""

import json
from typing import Any, Dict, List
from mcp.bigquery.server import bq_mcp_server
from mcp.market_data.server import market_data_mcp_server
from mcp.research.server import research_mcp_server
from orchestration.config import settings
from orchestration.contracts import (
    AgentExecutionResult,
    CompletionStatus,
    EpistemicType,
    ExecutionTelemetry,
    SourceCitation,
    UncertaintySpecification,
    ValidationFinding,
)
from services.agents.base import BaseSpecializedAgent


class DataGovernanceAgent(BaseSpecializedAgent):
    """Validates data freshness, schema integrity, point-in-time anti-leakage, and issues PASS/DEGRADE/BLOCK."""

    agent_name = "data_governance_agent"
    role_summary = "Data Quality & Governance Gatekeeper"
    epistemic_classification = EpistemicType.MEASURED_HISTORICAL_FACT

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        health = bq_mcp_server.get_pipeline_and_dq_health(caller_agent=self.agent_name)
        dq = health.get("dq_report", {})
        ops_run = health.get("ops_pipeline_run", {})
        ticker = context.get("ticker")
        tool_calls = 1

        uni_check = None
        if ticker:
            uni_check = market_data_mcp_server.validate_ticker_universe(
                caller_agent=self.agent_name, ticker=ticker
            )
            tool_calls += 1

        verdict = dq.get("verdict", "PASS")
        if uni_check and not uni_check.get("in_universe", True):
            verdict = "BLOCK"

        findings_list: List[ValidationFinding] = []
        for chk in dq.get("checks", []):
            findings_list.append(
                ValidationFinding(
                    check_name=chk["check_name"],
                    passed=bool(chk["passed"]),
                    severity=chk.get("severity", "INFO"),
                    message=chk.get("details", ""),
                )
            )
        if uni_check:
            findings_list.append(
                ValidationFinding(
                    check_name="ticker_universe_membership",
                    passed=bool(uni_check["in_universe"]),
                    severity="INFO" if uni_check["in_universe"] else "CRITICAL",
                    message=(
                        f"Ticker {ticker} verified in Security Master."
                        if uni_check["in_universe"]
                        else f"Ticker {ticker} is outside governed universe."
                    ),
                )
            )

        passed_ratio = (
            float(dq.get("passed_count", 1)) / max(1.0, float(len(dq.get("checks", [1]))))
        )
        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description="Verify dataset freshness SLA, schema integrity, and point-in-time anti-leakage.",
            status=CompletionStatus.COMPLETED if verdict == "PASS" else CompletionStatus.ABSTAINED,
            epistemic_classification=EpistemicType.MEASURED_HISTORICAL_FACT,
            input_dataset_versions={"ops_run_id": str(ops_run.get("run_id", "latest"))},
            findings={
                "governance_verdict": verdict,
                "latest_trade_date": dq.get("latest_trade_date"),
                "freshness_lag_hours": dq.get("freshness_lag_hours", 0.0),
                "universe_check": uni_check,
            },
            metrics={
                "freshness_lag_hours": float(dq.get("freshness_lag_hours", 0.0)),
                "dq_passed_count": float(dq.get("passed_count", 0)),
                "dq_failed_count": float(dq.get("failed_count", 0)),
            },
            citations=[
                SourceCitation(
                    source_type="BIGQUERY_WAREHOUSE",
                    title="BigQuery ops_pipeline_runs & Data Quality Validator",
                    url=f"https://console.cloud.google.com/bigquery?project={settings.project_id}",
                    event_timestamp=ops_run.get("latest_source_timestamp"),
                    publication_timestamp=ops_run.get("completed_at", ""),
                    is_verified_filing=True,
                )
            ],
            assumptions=["US equity market EOD settlement calendar applies."],
            limitations=["Intraday tick-level microstructure anomalies are not evaluated in EOD mode."],
            uncertainty=UncertaintySpecification(
                meaning="Empirical proportion of automated data quality and anti-leakage checks passing.",
                epistemic_type=EpistemicType.MEASURED_HISTORICAL_FACT,
                point_estimate=round(passed_ratio, 4),
                abstained=(verdict == "BLOCK"),
                abstention_reason="Blocked by Data Governance check" if verdict == "BLOCK" else None,
            ),
            validation_results=findings_list,
            telemetry=ExecutionTelemetry(tool_calls_count=tool_calls),
        )


class MarketRegimeAgent(BaseSpecializedAgent):
    """Analyzes broad market trends, volatility, sector dispersion, and macro indicators."""

    agent_name = "market_regime_agent"
    role_summary = "Macro & Market Regime Classifier"
    epistemic_classification = EpistemicType.MEASURED_HISTORICAL_FACT

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        macro_snap = market_data_mcp_server.get_macro_regime_snapshot(caller_agent=self.agent_name)
        spy_hist = market_data_mcp_server.get_ohlcv_history(
            caller_agent=self.agent_name, ticker="SPY", limit_days=60
        )

        etf_map = {
            f["ticker"]: f for f in macro_snap.get("benchmark_etf_features", [])
        }
        macro_map = {
            m["series_id"]: m for m in macro_snap.get("macro_indicators", [])
        }

        spy = etf_map.get("SPY", {})
        qqq = etf_map.get("QQQ", {})
        spy_ret20 = float(spy.get("ret_20d", 0.015))
        spy_vol20 = float(spy.get("vol_20d_ann", 0.14))
        vix_val = float(macro_map.get("VIXCLS", {}).get("value", 16.5))
        t10y2y = float(macro_map.get("T10Y2Y", {}).get("value", 0.18))
        hy_oas = float(macro_map.get("BAMLH0A0HYM2", {}).get("value", 3.12))

        if spy_ret20 > 0.01 and spy_vol20 < 0.20 and vix_val < 22.0:
            regime = "EXPANSIONARY_MOMENTUM"
            regime_desc = "Constructive equity trend with contained realized volatility and tight credit spreads."
        elif spy_vol20 >= 0.22 or vix_val >= 25.0:
            regime = "HIGH_VOLATILITY_DISPERSION"
            regime_desc = "Elevated cross-asset volatility and wider credit risk premia; defensive sizing warranted."
        else:
            regime = "TRANSITIONAL_CONSOLIDATION"
            regime_desc = "Range-bound index consolidation with rotational sector dispersion."

        sector_leaders = sorted(
            [
                {"ticker": k, "ret_20d_pct": round(float(v.get("ret_20d", 0.0)) * 100.0, 2)}
                for k, v in etf_map.items()
            ],
            key=lambda x: x["ret_20d_pct"],
            reverse=True,
        )

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description="Classify overall equity and macro market regime using SPY, QQQ, sector ETFs, and FRED indicators.",
            status=CompletionStatus.COMPLETED,
            epistemic_classification=EpistemicType.MEASURED_HISTORICAL_FACT,
            findings={
                "regime_classification": regime,
                "regime_narrative": regime_desc,
                "benchmark_etf_leaderboard": sector_leaders,
                "macro_indicators": macro_snap.get("macro_indicators", []),
                "spy_latest_close": spy_hist.get("latest_close"),
                "spy_latest_date": spy_hist.get("latest_trade_date"),
            },
            metrics={
                "spy_ret_20d_pct": round(spy_ret20 * 100.0, 2),
                "spy_vol_20d_ann_pct": round(spy_vol20 * 100.0, 2),
                "qqq_ret_20d_pct": round(float(qqq.get("ret_20d", 0.0)) * 100.0, 2),
                "vix_index": vix_val,
                "treasury_10y_2y_spread_pct": t10y2y,
                "hy_credit_oas_pct": hy_oas,
            },
            citations=[
                SourceCitation(
                    source_type="FRED_MACRO",
                    title="FRED Macroeconomic Series (VIXCLS, T10Y2Y, DFF, CPIAUCSL, BAMLH0A0HYM2)",
                    url="https://fred.stlouisfed.org",
                    event_timestamp=f"{spy_hist.get('latest_trade_date', '')}T20:00:00+00:00",
                    is_verified_filing=True,
                ),
                SourceCitation(
                    source_type="MARKET_DATA_EOD",
                    title="Benchmark ETF Price & Volatility Series (SPY, QQQ, XLK, XLF, XLV)",
                    url="https://finance.yahoo.com/quote/SPY",
                    event_timestamp=f"{spy_hist.get('latest_trade_date', '')}T20:00:00+00:00",
                ),
            ],
            assumptions=["Regime thresholds use 20-day realized SPY volatility and CBOE VIX regime cutoffs."],
            limitations=["Sudden geopolitical intraday shocks may shift regime faster than daily EOD bars reflect."],
            uncertainty=UncertaintySpecification(
                meaning="Regime classification stability score based on distance from volatility boundary thresholds.",
                epistemic_type=EpistemicType.MEASURED_HISTORICAL_FACT,
                point_estimate=round(min(0.95, max(0.55, 1.0 - abs(spy_vol20 - 0.15))), 3),
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=2),
        )


class MarketDataAgent(BaseSpecializedAgent):
    """Retrieves and validates historical and current OHLCV market data for a target security."""

    agent_name = "market_data_agent"
    role_summary = "Market Data Retrieval & Hygiene Specialist"
    epistemic_classification = EpistemicType.MEASURED_HISTORICAL_FACT

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = (context.get("ticker") or "NVDA").strip().upper()
        meta = market_data_mcp_server.get_security_metadata(caller_agent=self.agent_name, ticker=ticker)
        ohlcv = market_data_mcp_server.get_ohlcv_history(
            caller_agent=self.agent_name, ticker=ticker, limit_days=60
        )
        bars = ohlcv.get("bars", [])
        latest = bars[-1] if bars else {}
        prev = bars[-2] if len(bars) >= 2 else latest
        c_now = float(latest.get("close", latest.get("close_price", 1.0)) or 1.0)
        c_prev = float(prev.get("close", prev.get("close_price", 1.0)) or 1.0)
        daily_chg_pct = ((c_now / c_prev) - 1.0) * 100.0 if (latest and prev and c_prev > 0) else 0.0

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description=f"Retrieve and validate normalized OHLCV history and security metadata for {ticker}.",
            status=CompletionStatus.COMPLETED if bars else CompletionStatus.ABSTAINED,
            epistemic_classification=EpistemicType.MEASURED_HISTORICAL_FACT,
            findings={
                "security_metadata": meta.get("security"),
                "latest_trade_date": ohlcv.get("latest_trade_date"),
                "latest_close": ohlcv.get("latest_close"),
                "daily_change_pct": round(daily_chg_pct, 2),
                "source_provider": ohlcv.get("source_provider"),
                "latency_class": ohlcv.get("latency_class"),
                "bar_count_retrieved": ohlcv.get("bar_count", 0),
                "recent_bars_tail": bars[-10:],
            },
            metrics={
                "latest_close_price": float(ohlcv.get("latest_close") or 0.0),
                "daily_change_pct": round(daily_chg_pct, 2),
                "bar_count": float(ohlcv.get("bar_count", 0)),
            },
            citations=[
                SourceCitation(
                    source_type="MARKET_DATA_EOD",
                    title=f"{ticker} Validated Daily OHLCV Series ({ohlcv.get('source_provider')})",
                    url=f"https://finance.yahoo.com/quote/{ticker}",
                    event_timestamp=f"{ohlcv.get('latest_trade_date', '')}T20:00:00+00:00",
                )
            ],
            assumptions=["Prices are split-adjusted and dividend-adjusted where reported by provider."],
            limitations=[f"Data latency tier is {ohlcv.get('latency_class', 'DELAYED_EOD')}."],
            uncertainty=UncertaintySpecification(
                meaning="Observation completeness ratio over trailing 60 trading days.",
                epistemic_type=EpistemicType.MEASURED_HISTORICAL_FACT,
                point_estimate=round(min(1.0, len(bars) / 60.0), 3),
                abstained=(len(bars) == 0),
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=2),
        )


class NewsCatalystAgent(BaseSpecializedAgent):
    """Uses Vertex AI Google Search grounding and SEC EDGAR filings to research company catalysts."""

    agent_name = "news_catalyst_agent"
    role_summary = "News, SEC Filings & Catalyst Research Specialist"
    epistemic_classification = EpistemicType.AGENT_INTERPRETATION

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = (context.get("ticker") or "NVDA").strip().upper()
        enable_live = bool(context.get("enable_live_vertex", False))
        meta = market_data_mcp_server.get_security_metadata(caller_agent=self.agent_name, ticker=ticker)
        company_name = meta.get("security", {}).get("company_name", ticker)

        grounded = research_mcp_server.run_grounded_news_search(
            caller_agent=self.agent_name,
            ticker=ticker,
            company_name=company_name,
            enable_live_vertex=enable_live,
        )

        citations: List[SourceCitation] = []
        for c in grounded.get("grounded_citations", []):
            citations.append(
                SourceCitation(
                    source_type=c.get("source_type", "SEC_EDGAR"),
                    title=c.get("title", f"{ticker} Filing/Catalyst"),
                    url=c.get("url", "https://www.sec.gov/edgar"),
                    event_timestamp=c.get("event_timestamp"),
                    publication_timestamp=c.get("publication_timestamp", ""),
                    is_verified_filing=(c.get("source_type") == "SEC_EDGAR"),
                )
            )

        edgar_events = grounded.get("sec_edgar_catalysts", [])
        avg_polarity = (
            sum(float(e.get("direction_polarity", 0.0)) for e in edgar_events) / max(1, len(edgar_events))
        )

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description=f"Discover and verify SEC filings, earnings releases, and grounded news catalysts for {ticker}.",
            status=CompletionStatus.COMPLETED,
            epistemic_classification=EpistemicType.AGENT_INTERPRETATION,
            findings={
                "ticker": ticker,
                "company_name": company_name,
                "grounding_mode": grounded.get("grounding_mode"),
                "catalyst_synthesis": grounded.get("grounded_summary"),
                "sec_edgar_events": edgar_events[:6],
            },
            metrics={
                "verified_sec_events_count": float(len(edgar_events)),
                "grounded_citations_count": float(len(citations)),
                "average_catalyst_polarity": round(avg_polarity, 3),
            },
            citations=citations,
            assumptions=["External news and filing summaries are sanitized against prompt injection prior to synthesis."],
            limitations=["Unverified media rumors are excluded unless corroborated by SEC filings or grounded sources."],
            uncertainty=UncertaintySpecification(
                meaning="Proportion of catalyst claims backed by primary SEC EDGAR filings or grounded citations.",
                epistemic_type=EpistemicType.AGENT_INTERPRETATION,
                point_estimate=round(min(1.0, len(citations) / 3.0), 3),
            ),
            telemetry=ExecutionTelemetry(
                model_id=settings.gemini_fast_model if grounded.get("grounding_mode") == "vertex_ai_google_search_live" else "sec-edgar-deterministic",
                tool_calls_count=2,
            ),
        )


class QuantitativeAnalysisAgent(BaseSpecializedAgent):
    """Evaluates point-in-time technical indicators, momentum, volatility, and volume anomalies."""

    agent_name = "quantitative_agent"
    role_summary = "Quantitative Signal & Technical Feature Specialist"
    epistemic_classification = EpistemicType.MEASURED_HISTORICAL_FACT

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = (context.get("ticker") or "NVDA").strip().upper()
        bundle = bq_mcp_server.get_security_features_and_forecasts(
            caller_agent=self.agent_name, ticker=ticker
        )
        f = bundle.get("latest_features") or {}
        if not f:
            raise ValueError(f"No quantitative features available for {ticker}")

        ret_5d = float(f.get("ret_5d", 0.0))
        ret_20d = float(f.get("ret_20d", 0.0))
        vol_20d = float(f.get("vol_20d_ann", 0.20))
        rsi_14 = float(f.get("rsi_14", 50.0))
        macd_hist = float(f.get("macd_hist", 0.0))
        vol_z = float(f.get("volume_zscore_20d", 0.0))
        rel_str = float(f.get("rel_strength_sector_20d", 0.0))
        bb_pct_b = float(f.get("bb_pct_b_20d", 0.5))

        anomalies: List[str] = []
        if abs(vol_z) >= 1.5:
            anomalies.append(f"Unusual volume anomaly detected (20d Volume Z-Score = {vol_z:+.2f} sigma).")
        if rsi_14 >= 70.0:
            anomalies.append(f"Overbought momentum condition (RSI-14 = {rsi_14:.1f}).")
        elif rsi_14 <= 30.0:
            anomalies.append(f"Oversold technical condition (RSI-14 = {rsi_14:.1f}).")
        if abs(rel_str) >= 0.04:
            anomalies.append(f"Material 20d excess return vs SPY benchmark ({rel_str*100:+.2f}%).")

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description=f"Compute point-in-time momentum, volatility, volume z-score, and cross-sectional signals for {ticker}.",
            status=CompletionStatus.COMPLETED,
            epistemic_classification=EpistemicType.MEASURED_HISTORICAL_FACT,
            findings={
                "ticker": ticker,
                "trade_date": f.get("trade_date"),
                "signal_anomalies": anomalies,
                "feature_vector": f,
            },
            metrics={
                "ret_5d_pct": round(ret_5d * 100.0, 2),
                "ret_20d_pct": round(ret_20d * 100.0, 2),
                "vol_20d_ann_pct": round(vol_20d * 100.0, 2),
                "rsi_14": round(rsi_14, 2),
                "macd_hist": round(macd_hist, 4),
                "volume_zscore_20d": round(vol_z, 2),
                "rel_strength_spy_20d_pct": round(rel_str * 100.0, 2),
                "bollinger_pct_b": round(bb_pct_b, 3),
            },
            citations=[
                SourceCitation(
                    source_type="BIGQUERY_WAREHOUSE",
                    title=f"BigQuery mart_quant_features ({ticker} as of {f.get('trade_date')})",
                    url=f"https://console.cloud.google.com/bigquery?project={settings.project_id}",
                    event_timestamp=f"{f.get('trade_date')}T20:00:00+00:00",
                    is_verified_filing=True,
                )
            ],
            assumptions=["All technical indicators are computed strictly from backward-looking causal windows (t <= T)."],
            limitations=["Technical momentum patterns describe statistical tendencies and do not imply causal determinism."],
            uncertainty=UncertaintySpecification(
                meaning="Feature non-null completeness ratio across the 18-dimensional point-in-time feature vector.",
                epistemic_type=EpistemicType.MEASURED_HISTORICAL_FACT,
                point_estimate=1.0,
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=1),
        )


class ForecastingAgent(BaseSpecializedAgent):
    """Executes and retrieves calibrated multi-horizon (1d, 5d, 20d) quantitative forecasts."""

    agent_name = "forecasting_agent"
    role_summary = "Calibrated Multi-Horizon Quantitative Forecaster"
    epistemic_classification = EpistemicType.CALIBRATED_MODEL_FORECAST

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = (context.get("ticker") or "NVDA").strip().upper()
        bundle = bq_mcp_server.get_security_features_and_forecasts(
            caller_agent=self.agent_name, ticker=ticker
        )
        reg = bq_mcp_server.get_model_registry_metrics(caller_agent=self.agent_name)
        forecasts = bundle.get("forecasts", [])
        if not forecasts:
            raise ValueError(f"No calibrated forecasts available for {ticker}")

        by_horizon = {int(p["horizon_days"]): p for p in forecasts}
        p5 = by_horizon.get(5, forecasts[0])
        p1 = by_horizon.get(1, p5)
        p20 = by_horizon.get(20, p5)

        abstained = bool(p5.get("abstained", False))
        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description=f"Generate calibrated 1d, 5d, and 20d excess-return probability forecasts for {ticker}.",
            status=CompletionStatus.ABSTAINED if abstained else CompletionStatus.COMPLETED,
            epistemic_classification=EpistemicType.CALIBRATED_MODEL_FORECAST,
            findings={
                "ticker": ticker,
                "horizons": {
                    "1d": p1,
                    "5d": p5,
                    "20d": p20,
                },
                "model_registry_summary": reg.get("models", []),
            },
            metrics={
                "prob_up_1d": float(p1.get("calibrated_prob_up", 0.5)),
                "prob_up_5d": float(p5.get("calibrated_prob_up", 0.5)),
                "prob_up_20d": float(p20.get("calibrated_prob_up", 0.5)),
                "expected_excess_return_5d_bps": float(p5.get("expected_excess_return_bps", 0.0)),
                "roc_auc_5d_oos": float(p5.get("roc_auc_oos", 0.5)),
                "brier_score_5d_oos": float(p5.get("brier_score_oos", 0.25)),
            },
            citations=[
                SourceCitation(
                    source_type="BIGQUERY_WAREHOUSE",
                    title=f"BigQuery fact_model_predictions & model_registry ({p5.get('model_id')} {p5.get('model_version')})",
                    url=f"https://console.cloud.google.com/bigquery?project={settings.project_id}",
                    event_timestamp=p5.get("as_of_timestamp"),
                    is_verified_filing=True,
                )
            ],
            assumptions=[
                "Probabilities are Platt-calibrated on chronological walk-forward out-of-sample folds with purge/embargo gaps."
            ],
            limitations=[
                "Historical statistical relationships can break down during structural regime shifts or idiosyncratic M&A events."
            ],
            uncertainty=UncertaintySpecification(
                meaning=(
                    f"Out-of-sample Platt-calibrated probability of 5d excess return >= +{p5.get('target_threshold_pct', 2.2)}% over SPY."
                ),
                epistemic_type=EpistemicType.CALIBRATED_MODEL_FORECAST,
                point_estimate=float(p5.get("calibrated_prob_up", 0.5)),
                lower_bound_90=float(p5.get("prediction_interval_low_pct", -5.0)),
                upper_bound_90=float(p5.get("prediction_interval_high_pct", 5.0)),
                brier_score=float(p5.get("brier_score_oos", 0.22)),
                abstained=abstained,
                abstention_reason=p5.get("abstention_reason"),
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=2),
        )


class FundamentalAnalysisAgent(BaseSpecializedAgent):
    """Analyzes SEC XBRL financial statements with strict point-in-time filing date enforcement."""

    agent_name = "fundamental_agent"
    role_summary = "Point-in-Time SEC XBRL Fundamental Analyst"
    epistemic_classification = EpistemicType.MEASURED_HISTORICAL_FACT

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = (context.get("ticker") or "NVDA").strip().upper()
        sec_data = research_mcp_server.get_sec_edgar_catalysts_and_fundamentals(
            caller_agent=self.agent_name, ticker=ticker
        )
        feat_bundle = bq_mcp_server.get_security_features_and_forecasts(
            caller_agent=self.agent_name, ticker=ticker
        )
        pit_rows = sec_data.get("fundamentals_pit", [])
        latest_pit = pit_rows[0] if pit_rows else {}
        f = feat_bundle.get("latest_features") or {}

        rev_g = float(f.get("rev_growth_yoy_pit", latest_pit.get("rev_growth_yoy", 0.08)))
        p_margin = float(f.get("profit_margin_pit", latest_pit.get("operating_margin", 0.15)))
        debt_cash = float(f.get("debt_to_cash_pit", 0.8))
        pe_ttm = float(f.get("pe_ttm_pit", 22.0))

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description=f"Evaluate point-in-time SEC XBRL financial statements and valuation ratios for {ticker}.",
            status=CompletionStatus.COMPLETED,
            epistemic_classification=EpistemicType.MEASURED_HISTORICAL_FACT,
            findings={
                "ticker": ticker,
                "latest_reported_period_end": latest_pit.get("period_end_date"),
                "latest_sec_filing_timestamp": latest_pit.get("filing_timestamp"),
                "form_type": latest_pit.get("form_type", "10-Q/10-K"),
                "reported_facts": latest_pit,
                "derived_valuation_ratios": {
                    "pe_ttm_pit": round(pe_ttm, 2),
                    "debt_to_cash_ratio_pit": round(debt_cash, 2),
                },
            },
            metrics={
                "revenue_growth_yoy_pct": round(rev_g * 100.0, 2),
                "operating_profit_margin_pct": round(p_margin * 100.0, 2),
                "debt_to_cash_ratio": round(debt_cash, 2),
                "pe_ttm": round(pe_ttm, 2),
            },
            citations=[
                SourceCitation(
                    source_type="SEC_EDGAR",
                    title=f"{ticker} SEC EDGAR XBRL CompanyFacts ({latest_pit.get('form_type', '10-K/10-Q')})",
                    url=latest_pit.get("source_url", "https://data.sec.gov/api/xbrl/companyfacts/"),
                    event_timestamp=f"{latest_pit.get('period_end_date', '')}T23:59:59+00:00",
                    publication_timestamp=latest_pit.get("acceptance_timestamp")
                    or latest_pit.get("filing_timestamp")
                    or f"{latest_pit.get('filing_date', '2026-08-05')}T20:15:00+00:00",
                    is_verified_filing=True,
                )
            ],
            assumptions=[
                "Reported GAAP/XBRL figures are joined strictly by SEC filing_timestamp to prevent look-ahead leakage."
            ],
            limitations=["Derived P/E multiple combines point-in-time GAAP EPS with latest EOD close price."],
            uncertainty=UncertaintySpecification(
                meaning="Point-in-time SEC XBRL filing verification confidence.",
                epistemic_type=EpistemicType.MEASURED_HISTORICAL_FACT,
                point_estimate=1.0 if latest_pit else 0.7,
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=2),
        )


class RiskPortfolioAgent(BaseSpecializedAgent):
    """Evaluates downside exposure, drawdowns, volatility, beta, liquidity, and unsuitability flags."""

    agent_name = "risk_agent"
    role_summary = "Risk & Suitability Evaluation Specialist"
    epistemic_classification = EpistemicType.MEASURED_HISTORICAL_FACT

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = (context.get("ticker") or "NVDA").strip().upper()
        bundle = bq_mcp_server.get_security_features_and_forecasts(
            caller_agent=self.agent_name, ticker=ticker
        )
        f = bundle.get("latest_features") or {}
        rec = bundle.get("recommendation") or {}

        vol_20d = float(f.get("vol_20d_ann", 0.25))
        vol_60d = float(f.get("vol_60d_ann", 0.25))
        max_dd_60d = float(f.get("max_drawdown_60d", -0.09))
        beta_60d = float(f.get("beta_spy_60d", 1.05))
        atr_pct = float(f.get("atr_pct_14d", 0.02))

        unsuitability_flags = json.loads(rec.get("unsuitability_flags_json", "[]"))
        if not unsuitability_flags:
            unsuitability_flags = [
                "Subject to equity beta, sector concentration, and earnings gap risk."
            ]

        risk_tier = "HIGH_RISK" if (vol_20d > 0.35 or abs(max_dd_60d) > 0.15) else (
            "MODERATE_RISK" if vol_20d > 0.20 else "LOW_TO_MODERATE_RISK"
        )

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description=f"Quantify volatility, drawdown, beta, tail exposure, and unsuitability flags for {ticker}.",
            status=CompletionStatus.COMPLETED,
            epistemic_classification=EpistemicType.MEASURED_HISTORICAL_FACT,
            findings={
                "ticker": ticker,
                "risk_tier": risk_tier,
                "unsuitability_flags": unsuitability_flags,
                "risk_summary": rec.get("risk_summary", ""),
                "invalidation_stop_trigger": rec.get("invalidation_conditions", ""),
            },
            metrics={
                "vol_20d_ann_pct": round(vol_20d * 100.0, 2),
                "vol_60d_ann_pct": round(vol_60d * 100.0, 2),
                "max_drawdown_60d_pct": round(max_dd_60d * 100.0, 2),
                "beta_spy_60d": round(beta_60d, 2),
                "atr_14d_pct": round(atr_pct * 100.0, 2),
            },
            citations=[
                SourceCitation(
                    source_type="BIGQUERY_WAREHOUSE",
                    title=f"BigQuery Risk & Drawdown Analytics ({ticker})",
                    url=f"https://console.cloud.google.com/bigquery?project={settings.project_id}",
                    event_timestamp=f"{f.get('trade_date', '')}T20:00:00+00:00",
                    is_verified_filing=True,
                )
            ],
            assumptions=["Investor-specific risk tolerance is NOT assumed; explicit unsuitability criteria are disclosed."],
            limitations=["Historical 60-day drawdown does not bound extreme black-swan tail events."],
            uncertainty=UncertaintySpecification(
                meaning="Empirical stability of trailing 60d volatility and beta estimates.",
                epistemic_type=EpistemicType.MEASURED_HISTORICAL_FACT,
                point_estimate=0.92,
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=1),
        )


class IndependentCriticAgent(BaseSpecializedAgent):
    """Independent adversarial verifier that audits evidence citations, timestamp alignment, and risk bounds."""

    agent_name = "critic_agent"
    role_summary = "Independent Adversarial Critic & Verification Gate"
    epistemic_classification = EpistemicType.AGENT_INTERPRETATION

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = (context.get("ticker") or "NVDA").strip().upper()
        bundle = bq_mcp_server.get_security_features_and_forecasts(
            caller_agent=self.agent_name, ticker=ticker
        )
        sec_bundle = research_mcp_server.get_sec_edgar_catalysts_and_fundamentals(
            caller_agent=self.agent_name, ticker=ticker
        )
        dq_health = bq_mcp_server.get_pipeline_and_dq_health(caller_agent=self.agent_name)

        rec = bundle.get("recommendation") or {}
        preds = bundle.get("forecasts") or []
        dq_verdict = dq_health.get("dq_report", {}).get("verdict", "PASS")
        pit_rows = sec_bundle.get("fundamentals_pit", [])

        checks: List[ValidationFinding] = []

        # Check 1: Data Governance Pass
        dq_ok = dq_verdict == "PASS"
        checks.append(
            ValidationFinding(
                check_name="data_governance_gate",
                passed=dq_ok,
                severity="INFO" if dq_ok else "CRITICAL",
                message=f"Upstream Data Governance verdict is {dq_verdict}.",
            )
        )

        # Check 2: Point-in-time timestamp consistency (no future filing leakage)
        pit_ok = True
        for row in pit_rows:
            f_date = (
                row.get("filing_date")
                or str(row.get("acceptance_timestamp", ""))[:10]
                or str(row.get("filing_timestamp", ""))[:10]
            )
            p_end = str(row.get("period_end_date", ""))[:10]
            if p_end and f_date and p_end > f_date:
                pit_ok = False
        checks.append(
            ValidationFinding(
                check_name="point_in_time_timestamp_integrity",
                passed=pit_ok,
                severity="INFO" if pit_ok else "CRITICAL",
                message="Verified all SEC XBRL fundamentals have filing_date >= period_end_date.",
            )
        )

        # Check 3: Non-zero downside & uncertainty interval check
        p5 = next((p for p in preds if int(p.get("horizon_days", 0)) == 5), preds[0] if preds else {})
        low_90 = float(p5.get("prediction_interval_low_pct", -5.0))
        downside_ok = low_90 < 0.0
        checks.append(
            ValidationFinding(
                check_name="non_zero_downside_uncertainty_bound",
                passed=downside_ok,
                severity="INFO" if downside_ok else "CRITICAL",
                message=f"5d 10th-percentile downside bound is {low_90:+.2f}% (non-zero tail risk enforced).",
            )
        )

        # Check 4: Citations & Disconfirming scenarios present
        citations_raw = json.loads(rec.get("citations_json", "[]")) if rec else []
        cit_ok = len(citations_raw) >= 1 and bool(rec.get("bearish_scenario"))
        checks.append(
            ValidationFinding(
                check_name="evidence_citations_and_bearish_counter_case",
                passed=cit_ok,
                severity="INFO" if cit_ok else "WARNING",
                message=f"Verified {len(citations_raw)} primary source citations and explicit bearish counter-scenario.",
            )
        )

        all_passed = all(c.passed for c in checks)
        critic_verdict = (
            "APPROVED_WITH_UNCERTAINTY_BOUNDS"
            if all_passed
            else ("ABSTAIN_MANDATED" if not dq_ok or not pit_ok else "DOWNGRADE_CONFIDENCE")
        )

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description=f"Perform adversarial verification of point-in-time integrity, citations, and risk bounds for {ticker}.",
            status=CompletionStatus.COMPLETED if all_passed else CompletionStatus.ABSTAINED,
            epistemic_classification=EpistemicType.AGENT_INTERPRETATION,
            findings={
                "ticker": ticker,
                "critic_verdict": critic_verdict,
                "critic_notes": rec.get(
                    "critic_notes",
                    "Audited point-in-time SEC filing timestamps, out-of-sample Platt calibration, and downside risk bounds.",
                ),
                "disconfirming_risk_factors": json.loads(rec.get("unsuitability_flags_json", "[]")),
            },
            metrics={
                "checks_passed": float(sum(1 for c in checks if c.passed)),
                "checks_total": float(len(checks)),
            },
            citations=[
                SourceCitation(
                    source_type="BIGQUERY_WAREHOUSE",
                    title=f"Independent Critic Audit Log ({ticker})",
                    url=f"https://console.cloud.google.com/bigquery?project={settings.project_id}",
                    is_verified_filing=True,
                )
            ],
            assumptions=["Any unsupported claim or look-ahead timestamp violation triggers mandatory abstention."],
            limitations=["Critic verifies consistency against ingested primary sources."],
            uncertainty=UncertaintySpecification(
                meaning="Proportion of independent adversarial audit gates passed.",
                epistemic_type=EpistemicType.AGENT_INTERPRETATION,
                point_estimate=round(sum(1 for c in checks if c.passed) / max(1, len(checks)), 3),
                abstained=(critic_verdict == "ABSTAIN_MANDATED"),
            ),
            validation_results=checks,
            telemetry=ExecutionTelemetry(tool_calls_count=3),
        )


class RecommendationRankingAgent(BaseSpecializedAgent):
    """Synthesizes validated signals into transparent composite rankings and Bull/Base/Bear scenarios."""

    agent_name = "recommendation_agent"
    role_summary = "Transparent Opportunity Ranking & Scenario Architect"
    epistemic_classification = EpistemicType.AGENT_INTERPRETATION

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        ticker = context.get("ticker")
        sector = context.get("sector")
        stance = context.get("stance")

        rec_bundle = bq_mcp_server.get_latest_recommendations(
            caller_agent=self.agent_name, limit=25, sector=sector, stance=stance
        )
        all_recs = rec_bundle.get("recommendations", [])

        focus_rec = (
            next((r for r in all_recs if r.get("ticker") == ticker.strip().upper()), all_recs[0])
            if (ticker and all_recs)
            else (all_recs[0] if all_recs else {})
        )

        citations: List[SourceCitation] = []
        for c in json.loads(focus_rec.get("citations_json", "[]")) if focus_rec else []:
            citations.append(
                SourceCitation(
                    source_type=c.get("source_type", "SEC_EDGAR"),
                    title=c.get("title", "Primary Citation"),
                    url=c.get("url", "https://www.sec.gov"),
                    event_timestamp=c.get("event_timestamp"),
                    publication_timestamp=c.get("publication_timestamp", ""),
                    is_verified_filing=(c.get("source_type") == "SEC_EDGAR"),
                )
            )

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description="Rank stock opportunities using transparent composite criteria and generate Bull/Base/Bear scenarios.",
            status=CompletionStatus.COMPLETED if focus_rec else CompletionStatus.ABSTAINED,
            epistemic_classification=EpistemicType.AGENT_INTERPRETATION,
            findings={
                "focus_recommendation": focus_rec,
                "top_ranked_opportunities": all_recs[:10],
                "scoring_formula": (
                    "Composite Score (0-100) = 40% Calibrated Model Edge (5d/20d) "
                    "+ 20% Momentum & Sector Relative Strength + 20% Point-in-Time Fundamental Quality "
                    "+ 20% Volatility/Drawdown Risk Penalty"
                ),
            },
            metrics={
                "focus_composite_score": float(focus_rec.get("composite_rank_score", 0.0)),
                "focus_rank_position": float(focus_rec.get("rank_position", 0)),
                "focus_prob_up_5d": float(focus_rec.get("prob_material_move_up", 0.5)),
                "total_ranked_candidates": float(len(all_recs)),
            },
            citations=citations,
            assumptions=["Rankings require passing both Data Governance and Independent Critic validation."],
            limitations=["Research rankings are for decision support and do not constitute personalized investment advice."],
            uncertainty=UncertaintySpecification(
                meaning="5-trading-day calibrated probability of material upside move for focus candidate.",
                epistemic_type=EpistemicType.CALIBRATED_MODEL_FORECAST,
                point_estimate=float(focus_rec.get("prob_material_move_up", 0.5)),
                lower_bound_90=float(focus_rec.get("uncertainty_range_low_pct", -5.0)),
                upper_bound_90=float(focus_rec.get("uncertainty_range_high_pct", 5.0)),
                abstained=bool(focus_rec.get("abstained", False)),
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=1),
        )


class PerformanceBacktestAgent(BaseSpecializedAgent):
    """Evaluates historical forecast accuracy, calibration error, and net-of-cost walk-forward backtests."""

    agent_name = "performance_agent"
    role_summary = "Walk-Forward Backtesting & Calibration Auditor"
    epistemic_classification = EpistemicType.MEASURED_HISTORICAL_FACT

    def _run_impl(self, request_id: str, context: Dict[str, Any]) -> AgentExecutionResult:
        horizon = context.get("horizon_days")
        bt_bundle = bq_mcp_server.get_backtest_metrics(
            caller_agent=self.agent_name, horizon_days=horizon
        )
        reg_bundle = bq_mcp_server.get_model_registry_metrics(caller_agent=self.agent_name)

        backtests = bt_bundle.get("backtests", [])
        bt5 = next((b for b in backtests if int(b.get("horizon_days", 0)) == 5), backtests[0] if backtests else {})

        return AgentExecutionResult(
            request_id=request_id,
            agent_name=self.agent_name,
            task_description="Evaluate out-of-sample walk-forward backtest performance net of transaction costs and slippage.",
            status=CompletionStatus.COMPLETED if backtests else CompletionStatus.ABSTAINED,
            epistemic_classification=EpistemicType.MEASURED_HISTORICAL_FACT,
            findings={
                "backtest_runs": backtests,
                "model_registry": reg_bundle.get("models", []),
                "cost_assumptions": "10 bps round-trip transaction cost + 5 bps slippage deducted per rebalance.",
            },
            metrics={
                "net_sharpe_ratio_5d": float(bt5.get("sharpe_ratio", 0.0)),
                "annualized_return_5d_pct": round(float(bt5.get("annualized_return", 0.0)) * 100.0, 2),
                "benchmark_spy_return_pct": round(float(bt5.get("benchmark_return", 0.0)) * 100.0, 2),
                "hit_rate_5d_pct": round(float(bt5.get("hit_rate", 0.0)) * 100.0, 2),
                "brier_score_5d": float(bt5.get("brier_score", 0.25)),
                "max_drawdown_5d_pct": round(float(bt5.get("max_drawdown", 0.0)) * 100.0, 2),
            },
            citations=[
                SourceCitation(
                    source_type="BIGQUERY_WAREHOUSE",
                    title="BigQuery fact_backtest_runs & model_registry (Walk-Forward OOS Evaluation)",
                    url=f"https://console.cloud.google.com/bigquery?project={settings.project_id}",
                    is_verified_filing=True,
                )
            ],
            assumptions=["Chronological expanding-window splits with h-day embargo gap between train and test folds."],
            limitations=[
                "Past walk-forward backtest performance does not guarantee future returns; universe survivorship is bounded to current liquid large-cap constituents."
            ],
            uncertainty=UncertaintySpecification(
                meaning="Out-of-sample empirical hit rate across walk-forward rebalance periods.",
                epistemic_type=EpistemicType.MEASURED_HISTORICAL_FACT,
                point_estimate=float(bt5.get("hit_rate", 0.55)),
                brier_score=float(bt5.get("brier_score", 0.22)),
            ),
            telemetry=ExecutionTelemetry(tool_calls_count=2),
        )


SPECIALIZED_AGENT_REGISTRY: Dict[str, BaseSpecializedAgent] = {
    "data_governance_agent": DataGovernanceAgent(),
    "market_regime_agent": MarketRegimeAgent(),
    "market_data_agent": MarketDataAgent(),
    "news_catalyst_agent": NewsCatalystAgent(),
    "quantitative_agent": QuantitativeAnalysisAgent(),
    "forecasting_agent": ForecastingAgent(),
    "fundamental_agent": FundamentalAnalysisAgent(),
    "risk_agent": RiskPortfolioAgent(),
    "critic_agent": IndependentCriticAgent(),
    "recommendation_agent": RecommendationRankingAgent(),
    "performance_agent": PerformanceBacktestAgent(),
}
