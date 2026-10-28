# BigQuery Dataset & 13-Table Data Dictionary

**GCP Project**: `qwiklabs-gcp-03-c81d344a3430`  
**Dataset ID**: `market_intelligence`  
**Location**: `us-central1`

All 13 tables are provisioned with time partitioning and clustering to enforce cost-bounded analytical queries (`maximum_bytes_billed = 100 MB` per MCP query).

| # | Table Name | Partition Field | Cluster Fields | Purpose & Point-in-Time Contract |
|---|---|---|---|---|
| 1 | `raw_market_bars_daily` | `trade_date` (DAY) | `ticker`, `source` | Daily adjusted & unadjusted OHLCV bars, volume, dollar volume, and ingestion timestamp (`ingested_at`). |
| 2 | `reference_tickers` | — | `ticker`, `sector` | Security master metadata (CIK, company name, GICS sector, industry, benchmark flag, liquidity tier). |
| 3 | `fundamental_snapshots` | `filing_date` (MONTH) | `ticker`, `form_type` | SEC EDGAR XBRL fundamentals (`10-K`, `10-Q`) strictly indexed by `filing_date` (public release date) alongside `period_end_date`. |
| 4 | `corporate_events_and_filings` | `event_date` (MONTH) | `ticker`, `event_type` | SEC filings (`8-K`, `10-K`, `10-Q`), earnings releases, and catalyst events distinguishing `event_timestamp` from `published_timestamp`. |
| 5 | `news_and_catalysts` | `published_date` (DAY) | `ticker`, `catalyst_category` | Grounded financial news, citations, URLs, sentiment direction, and duplicate cluster IDs. |
| 6 | `macro_series` | `observation_date` (MONTH) | `series_id` | Macroeconomic indicators (`FEDFUNDS`, `CPIAUCSL`, `DGS10`, `T10Y2Y`, `VIXCLS`, `UNRATE`) with release date provenance. |
| 7 | `engineered_features_daily` | `trade_date` (DAY) | `ticker`, `feature_version` | Point-in-time feature store (`v1.0-pit`) containing 18 technical, volatility, relative-strength, and PIT fundamental features. |
| 8 | `market_regime_history` | `trade_date` (MONTH) | `regime_label` | Daily market regime classification (`BULL_LOW_VOL`, `BULL_HIGH_VOL`, `TRANSITIONAL_CHOP`, `BEAR_RISK_OFF`), breadth, and dispersion metrics. |
| 9 | `model_registry` | `trained_date` (MONTH) | `model_id`, `horizon` | Versioned quantitative models, training windows, feature lists, hyperparameters, out-of-sample Brier scores, and ROC-AUC. |
| 10 | `model_predictions_daily` | `prediction_date` (DAY) | `ticker`, `horizon`, `model_id` | Multi-horizon (`1d`, `5d`, `20d`) calibrated probabilities, expected returns, `10%-90%` intervals, top drivers, and abstention flags. |
| 11 | `ranked_recommendations` | `as_of_date` (DAY) | `ticker`, `conviction_tier` | Transparent multi-factor opportunity scores, bullish/base/bearish scenario trees, risk suitability flags, and Critic review status. |
| 12 | `backtest_runs` | `run_date` (MONTH) | `strategy_id`, `horizon` | Walk-forward net-of-cost backtest summaries (CAGR, Sharpe, Sortino, Max Drawdown, Hit Rate, Brier Score, IC, and benchmark alpha). |
| 13 | `agent_execution_audit_log` | `execution_date` (DAY) | `trace_id`, `agent_name`, `status` | Immutable audit trail of Root Agent, Orchestrator, and Specialist Agent executions, latency, token usage, and Critic vetoes. |
