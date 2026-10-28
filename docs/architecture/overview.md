# System Architecture, Agent Hierarchy & Quantitative Methodology

## 1. Hierarchical Agent System (`google-adk` + Bounded Orchestrator)

The intelligence layer implements a strict four-level hierarchy designed for auditability, deterministic fallback, and epistemic safety:

1. **Root Agent (`services/root_agent/agent.py`)**:
   - Primary entry point for `/api/v1/agent/research` and interactive queries.
   - Classifies user intent into one of 6 canonical categories (`MARKET_SUMMARY`, `OPPORTUNITY_SCAN`, `STOCK_DEEP_DIVE`, `CATALYST_RESEARCH`, `RISK_SUITABILITY_CHECK`, `PERFORMANCE_AUDIT`).
   - Wraps orchestration via Google Agent Development Kit (`google.adk.agents.Agent`) when live Vertex AI Gemini inference is invoked, with deterministic structural verification.
2. **Dynamic Bounded Orchestrator (`services/orchestrator/engine.py`)**:
   - Constructs a task-specific **Execution Plan (`OrchestratorExecutionPlan`)** from an immutable agent registry (`AGENT_TOOL_ALLOWLIST`).
   - Executes independent specialist agents in parallel stages (`ThreadPoolExecutor` with configurable concurrency and per-agent timeouts) while enforcing strict DAG dependencies:
     - **Stage 1 (Parallel Evidence Gathering)**: `data_governance_agent`, `market_regime_agent`, `market_data_agent`, `news_catalyst_agent`, `quantitative_agent`, `fundamental_agent`, `performance_agent`.
     - **Stage 2 (Model Inference & Risk Evaluation)**: `forecasting_agent`, `risk_agent`.
     - **Stage 3 (Independent Adversarial Audit)**: `critic_agent`.
     - **Stage 4 (Scenario & Recommendation Synthesis)**: `recommendation_agent` (gated by `critic_agent` verification and `risk_agent` suitability flags).
3. **11 Specialized Agents (`services/agents/specialists.py`)**:
   - Each agent operates under a strict tool allowlist enforced by `mcp/security.py`, emits a typed `AgentOutputEnvelope`, and attaches provenance citations and epistemic tags (`FACT`, `FORECAST`, `INTERPRETATION`, `HYPOTHESIS`).
4. **Independent Critic Veto Gate (`critic_agent`)**:
   - Inspects cross-agent claims for data staleness, insufficient calibration (`Brier > 0.25`), ungrounded catalysts, or extreme tail drawdown risk.
   - Can downgrade conviction (`HIGH` $\rightarrow$ `LOW` or `ABSTAIN`) before `recommendation_agent` publishes scenarios.

---

## 2. Quantitative Feature Store & Walk-Forward Forecasting

### Point-in-Time Feature Engineering (`data/features/engineer.py`, version `v1.0-pit`)
To eliminate look-ahead bias, all 18 technical, cross-sectional, fundamental, and macroeconomic features are computed strictly using observations available on or before `trade_date`:
- **Momentum & Trend**: `ret_1d`, `ret_5d`, `ret_20d`, `ret_60d`, `sma_20_dist`, `sma_50_dist`, `sma_200_dist`, `rsi_14`, `macd_hist`.
- **Volatility & Tail Risk**: `vol_20d` (annualized), `atr_14_pct`, `max_dd_60d`.
- **Liquidity & Participation**: `rel_volume_20d`, `dollar_volume_20d_m`.
- **Cross-Sectional Relative Strength**: `rs_vs_spy_20d`, `sector_rel_ret_20d`.
- **Point-in-Time Fundamentals & Macro**: Fundamental metrics from SEC EDGAR XBRL (`revenue_growth_yoy`, `operating_margin`, `debt_to_equity`) are gated by `filing_date <= trade_date` (never `period_end_date`), ensuring zero restatement or reporting-lag leakage.

### Multi-Horizon Probabilistic Models (`models/training/trainer.py`)
- **Horizons**:
  - `1d`: Next trading day material move (`|R_{t+1}| >= 1.5%` and directional upward probability `P(R_{t+1} > 0)`).
  - `5d`: 5-trading-day directional move (`R_{t+5} > +2.0%`).
  - `20d`: 20-trading-day trend continuation (`R_{t+20} > +4.0%`).
- **Walk-Forward Splitting**: Purged expanding-window walk-forward validation with an explicit embargo equal to the forecast horizon (`1`, `5`, or `20` trading days) between training folds and validation folds.
- **Calibration**: Raw log-odds scores are calibrated via **Platt Scaling (Sigmoid Calibration)** on out-of-sample walk-forward folds and evaluated against two mandatory baselines:
  1. Historical base-rate climatology (`Brier_baseline`)
  2. 20-day momentum persistence baseline
- **Abstention Policy**: If `brier_score > 0.25`, feature completeness `< 0.90`, or data staleness exceeds threshold, the `forecasting_agent` sets `abstain = True` and refuses to emit a directional signal.

---

## 3. Net-of-Cost Walk-Forward Backtesting (`models/backtesting/engine.py`)

All historical strategy evaluations include:
- **Transaction Cost Penalty**: `10.0 bps` per turnover event (`transaction_cost_bps = 10.0`).
- **Execution Slippage Penalty**: `5.0 bps` (`slippage_bps = 5.0`), totaling `15.0 bps` one-way friction.
- **Documented Limitations**: Universe survivorship bias is mitigated by including defensive, cyclical, energy, financial, healthcare, and high-volatility equities across multiple market regimes, and clearly disclosing universe constraints in every backtest report.
