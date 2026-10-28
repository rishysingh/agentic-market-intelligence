/**
 * TypeScript Data Contracts for the Agentic Stock Market Intelligence Terminal (`src/types/market.ts`).
 */

export interface CitationItem {
  source_type: string;
  title: string;
  url: string;
  event_timestamp?: string;
  publication_timestamp?: string;
}

export interface ScoreBreakdown {
  model_edge_score: number;
  momentum_score: number;
  fundamental_score: number;
  risk_penalty_score: number;
  prob_1d_up: number;
  prob_5d_up: number;
  prob_20d_up: number;
}

export interface OpportunityItem {
  recommendation_id: string;
  security_id: string;
  ticker: string;
  company_name?: string;
  sector: string;
  generated_date: string;
  as_of_timestamp: string;
  latest_price?: number;
  price_source?: string;
  primary_horizon_days: number;
  composite_rank_score: number;
  rank_position: number;
  research_stance: string;
  prob_material_move_up: number;
  prob_material_move_down: number;
  expected_excess_return_bps: number;
  uncertainty_range_low_pct: number;
  uncertainty_range_high_pct: number;
  market_regime_label: string;
  bullish_scenario: string;
  base_scenario: string;
  bearish_scenario: string;
  invalidation_conditions: string;
  risk_summary?: string;
  critic_status: string;
  critic_notes: string;
  model_version: string;
  data_freshness_status: string;
  abstained: boolean;
  score_breakdown?: ScoreBreakdown;
  unsuitability_flags?: string[];
  citations?: CitationItem[];
}

export interface HorizonForecast {
  prediction_id: string;
  ticker: string;
  as_of_date: string;
  horizon_days: number;
  target_definition: string;
  target_threshold_pct: number;
  calibrated_prob_up: number;
  calibrated_prob_down: number;
  expected_excess_return_bps: number;
  prediction_interval_low_pct: number;
  prediction_interval_high_pct: number;
  signal_direction: string;
  model_id: string;
  model_version: string;
  roc_auc_oos?: number;
  brier_score_oos?: number;
  abstained: boolean;
  abstention_reason?: string | null;
  top_features?: Array<{ feature: string; importance_weight: number; z_value?: number }>;
}

export interface OhlcvBar {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adj_close: number;
  volume: number;
  source_provider?: string;
}

export interface StockDossierResponse {
  as_of_utc: string;
  ticker: string;
  security: {
    security_id: string;
    ticker: string;
    company_name: string;
    cik: string;
    sector: string;
    industry: string;
    exchange: string;
  };
  price_history: {
    source_provider: string;
    latency_class: string;
    latest_trade_date: string;
    latest_close: number;
    bars: OhlcvBar[];
  };
  latest_quant_features: Record<string, number | string>;
  forecasts_by_horizon: HorizonForecast[];
  recommendation_and_scenarios: OpportunityItem;
  sec_edgar_catalysts: Array<{
    event_id: string;
    event_date: string;
    event_timestamp: string;
    publication_timestamp: string;
    catalyst_type: string;
    headline: string;
    summary: string;
    direction: string;
    source_name: string;
    source_url: string;
  }>;
  fundamentals_point_in_time: Array<{
    metric_name: string;
    metric_value: number;
    unit: string;
    fiscal_year: number;
    fiscal_period: string;
    form_type: string;
    period_end_date: string;
    filing_date: string;
    acceptance_timestamp: string;
    source_url: string;
  }>;
}
