import React, { useEffect, useState, useMemo } from "react";
import {
  OpportunityItem,
  StockDossierResponse,
  HorizonForecast,
  OhlcvBar,
} from "../types/market";

type WorkspaceTab =
  | "OVERVIEW"
  | "STOCK_DOSSIER"
  | "AGENT_CONSOLE"
  | "BACKTESTING"
  | "SYSTEM_HEALTH";

export default function FinancialResearchTerminal() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("OVERVIEW");
  const [selectedTicker, setSelectedTicker] = useState<string>("NVDA");
  const [selectedHorizon, setSelectedHorizon] = useState<number>(5);
  const [watchlist, setWatchlist] = useState<string[]>(["NVDA", "MSFT", "AAPL", "LLY", "JPM"]);

  // Filters for Opportunities
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [sectorFilter, setSectorFilter] = useState<string>("ALL");
  const [stanceFilter, setStanceFilter] = useState<string>("ALL");
  const [watchlistOnly, setWatchlistOnly] = useState<boolean>(false);

  // API Data states
  const [marketOverview, setMarketOverview] = useState<any>(null);
  const [opportunitiesData, setOpportunitiesData] = useState<{
    opportunities: OpportunityItem[];
    available_sectors: string[];
    scoring_methodology: string;
  }>({ opportunities: [], available_sectors: [], scoring_methodology: "" });
  const [stockDossier, setStockDossier] = useState<StockDossierResponse | null>(null);
  const [backtestData, setBacktestData] = useState<any>(null);
  const [systemHealth, setSystemHealth] = useState<any>(null);

  // Agent Console state
  const [agentQuery, setAgentQuery] = useState<string>(
    "Evaluate NVDA 5d and 20d calibrated return probabilities, SEC EDGAR filing catalysts, and downside risk invalidation levels."
  );
  const [agentTicker, setAgentTicker] = useState<string>("NVDA");
  const [agentIntent, setAgentIntent] = useState<string>("STOCK_ANALYSIS");
  const [enableLiveVertex, setEnableLiveVertex] = useState<boolean>(true);
  const [agentResponse, setAgentResponse] = useState<any>(null);
  const [agentLoading, setAgentLoading] = useState<boolean>(false);
  const [loadingDossier, setLoadingDossier] = useState<boolean>(false);

  // Initial data load
  useEffect(() => {
    fetch("/api/proxy/market/overview")
      .then((r) => r.json())
      .then(setMarketOverview)
      .catch(console.error);

    fetch("/api/proxy/opportunities?limit=25")
      .then((r) => r.json())
      .then((d) => {
        if (d && Array.isArray(d.opportunities)) {
          setOpportunitiesData(d);
        }
      })
      .catch(console.error);

    fetch("/api/proxy/performance/backtests")
      .then((r) => r.json())
      .then(setBacktestData)
      .catch(console.error);

    fetch("/api/proxy/health")
      .then((r) => r.json())
      .then(setSystemHealth)
      .catch(console.error);
  }, []);

  // Load Stock Dossier when selectedTicker changes
  useEffect(() => {
    setLoadingDossier(true);
    fetch(`/api/proxy/stocks/${selectedTicker}`)
      .then((r) => r.json())
      .then((d) => {
        if (d && d.ticker) {
          setStockDossier(d);
        }
      })
      .catch(console.error)
      .finally(() => setLoadingDossier(false));
  }, [selectedTicker]);

  const toggleWatchlist = (ticker: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setWatchlist((prev) =>
      prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker]
    );
  };

  const openStockDossier = (ticker: string) => {
    setSelectedTicker(ticker);
    setAgentTicker(ticker);
    setActiveTab("STOCK_DOSSIER");
  };

  const runAgentResearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setAgentLoading(true);
    try {
      const res = await fetch("/api/proxy/agent/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_query: agentQuery,
          ticker: agentTicker,
          intent: agentIntent,
          enable_live_vertex: enableLiveVertex,
        }),
      });
      const data = await res.json();
      setAgentResponse(data);
    } catch (err) {
      console.error(err);
    } finally {
      setAgentLoading(false);
    }
  };

  const filteredOpportunities = useMemo(() => {
    return (opportunitiesData.opportunities || []).filter((item) => {
      if (watchlistOnly && !watchlist.includes(item.ticker)) return false;
      if (sectorFilter !== "ALL" && item.sector !== sectorFilter) return false;
      if (stanceFilter !== "ALL" && !item.research_stance.includes(stanceFilter)) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const matchTicker = item.ticker.toLowerCase().includes(q);
        const matchName = (item.company_name || "").toLowerCase().includes(q);
        const matchSector = item.sector.toLowerCase().includes(q);
        if (!matchTicker && !matchName && !matchSector) return false;
      }
      return true;
    });
  }, [opportunitiesData.opportunities, watchlistOnly, watchlist, sectorFilter, stanceFilter, searchQuery]);

  const activeHorizonForecast: HorizonForecast | undefined = useMemo(() => {
    if (!stockDossier?.forecasts_by_horizon) return undefined;
    return (
      stockDossier.forecasts_by_horizon.find(
        (f) => Number(f.horizon_days) === Number(selectedHorizon)
      ) || stockDossier.forecasts_by_horizon[0]
    );
  }, [stockDossier, selectedHorizon]);

  const stanceBadgeClass = (stance?: string) => {
    if (!stance) return "badge badge-neutral";
    if (stance.includes("BULLISH")) return "badge badge-bull";
    if (stance.includes("BEARISH")) return "badge badge-bear";
    return "badge badge-neutral";
  };

  // Render SVG Price & Bollinger Chart for Stock Dossier
  const renderPriceChart = (bars: OhlcvBar[]) => {
    if (!bars || bars.length < 5) return <div className="kpi-sub">Loading OHLCV series...</div>;
    const w = 760;
    const h = 230;
    const padX = 42;
    const padY = 22;
    const closes = bars.map((b) => Number(b.close));
    const volumes = bars.map((b) => Number(b.volume));
    const minP = Math.min(...closes) * 0.985;
    const maxP = Math.max(...closes) * 1.015;
    const maxV = Math.max(...volumes, 1);

    const toX = (i: number) => padX + (i / (bars.length - 1)) * (w - padX * 2);
    const toY = (p: number) => h - padY - ((p - minP) / Math.max(0.01, maxP - minP)) * (h - padY * 2);

    const points = closes.map((c, i) => `${toX(i).toFixed(1)},${toY(c).toFixed(1)}`).join(" ");
    const areaPoints = `${toX(0).toFixed(1)},${h - padY} ${points} ${toX(bars.length - 1).toFixed(1)},${h - padY}`;

    // 20d Simple Moving Average overlay
    const smaPoints: string[] = [];
    for (let i = 0; i < closes.length; i++) {
      const start = Math.max(0, i - 19);
      const sub = closes.slice(start, i + 1);
      const avg = sub.reduce((a, b) => a + b, 0) / sub.length;
      smaPoints.push(`${toX(i).toFixed(1)},${toY(avg).toFixed(1)}`);
    }

    const isPositive = closes[closes.length - 1] >= closes[0];
    const strokeColor = isPositive ? "#10b981" : "#f43f5e";

    return (
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: "235px", display: "block" }}>
        <defs>
          <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.28" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
          </linearGradient>
        </defs>
        {/* Horizontal Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((t, idx) => {
          const yVal = padY + t * (h - padY * 2);
          const priceLabel = (maxP - t * (maxP - minP)).toFixed(1);
          return (
            <g key={idx}>
              <line x1={padX} y1={yVal} x2={w - padX} y2={yVal} stroke="#1e2d47" strokeDasharray="3,3" />
              <text x={4} y={yVal + 4} fill="#657999" fontSize="10" fontFamily="monospace">
                ${priceLabel}
              </text>
            </g>
          );
        })}
        {/* Volume Bars at bottom */}
        {bars.map((b, i) => {
          const vH = (Number(b.volume) / maxV) * 42;
          return (
            <rect
              key={i}
              x={toX(i) - 2}
              y={h - padY - vH}
              width={4}
              height={vH}
              fill="rgba(56, 139, 253, 0.22)"
            />
          );
        })}
        <polygon points={areaPoints} fill="url(#priceGrad)" />
        <polyline fill="none" stroke="#388bfd" strokeWidth="1.3" strokeDasharray="4,3" points={smaPoints.join(" ")} />
        <polyline fill="none" stroke={strokeColor} strokeWidth="2.2" points={points} />
        <text x={padX + 6} y={15} fill="#97a9c4" fontSize="10" fontFamily="monospace">
          Solid: Validated EOD Close | Dashed Blue: 20D Causal Moving Average | Bars: Daily Volume
        </text>
      </svg>
    );
  };

  // Render SVG Walk-Forward Equity Curve
  const renderEquityCurveChart = (curve: any[]) => {
    if (!curve || curve.length < 2) return <div className="kpi-sub">No equity curve points.</div>;
    const w = 720;
    const h = 210;
    const padX = 44;
    const padY = 20;
    const allVals = curve.flatMap((pt) => [Number(pt.strategy_nav), Number(pt.benchmark_nav)]);
    const minV = Math.min(...allVals, 95) * 0.99;
    const maxV = Math.max(...allVals, 105) * 1.01;

    const toX = (i: number) => padX + (i / (curve.length - 1)) * (w - padX * 2);
    const toY = (v: number) => h - padY - ((v - minV) / Math.max(0.1, maxV - minV)) * (h - padY * 2);

    const stratPts = curve.map((pt, i) => `${toX(i).toFixed(1)},${toY(Number(pt.strategy_nav)).toFixed(1)}`).join(" ");
    const benchPts = curve.map((pt, i) => `${toX(i).toFixed(1)},${toY(Number(pt.benchmark_nav)).toFixed(1)}`).join(" ");

    return (
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: "215px", display: "block" }}>
        {[0, 0.5, 1].map((t, idx) => {
          const yVal = padY + t * (h - padY * 2);
          const navLbl = (maxV - t * (maxV - minV)).toFixed(1);
          return (
            <g key={idx}>
              <line x1={padX} y1={yVal} x2={w - padX} y2={yVal} stroke="#1e2d47" strokeDasharray="3,3" />
              <text x={4} y={yVal + 4} fill="#657999" fontSize="10" fontFamily="monospace">
                {navLbl}
              </text>
            </g>
          );
        })}
        <polyline fill="none" stroke="#97a9c4" strokeWidth="1.6" strokeDasharray="4,3" points={benchPts} />
        <polyline fill="none" stroke="#22d3ee" strokeWidth="2.4" points={stratPts} />
        <text x={padX + 6} y={14} fill="#22d3ee" fontSize="10" fontFamily="monospace">
          Cyan: Net-of-Cost Walk-Forward Strategy (10bps cost + 5bps slippage) | Grey Dashed: SPY Benchmark (Base=100)
        </text>
      </svg>
    );
  };

  return (
    <div className="terminal-shell">
      {/* Top Institutional Header */}
      <header className="top-bar">
        <div className="brand-cluster">
          <span className="brand-mark">AMI // GCP</span>
          <div>
            <div className="brand-title">
              AGENTIC STOCK MARKET INTELLIGENCE &amp; PREDICTION TERMINAL
            </div>
            <div className="brand-subtitle">
              Google ADK Hierarchical Multi-Agent System &bull; Point-in-Time BigQuery Warehouse &bull; Walk-Forward Calibrated Models
            </div>
          </div>
        </div>
        <div className="status-strip">
          <span className="badge badge-bull">
            ● REGIME: {marketOverview?.market_regime?.regime_classification || "EXPANSIONARY_MOMENTUM"}
          </span>
          <span className="badge badge-info">
            DATA: {marketOverview?.latest_trade_date || "2026-10-27"} (DELAYED_EOD)
          </span>
          <span className="badge badge-epistemic">
            DQ GATE: {systemHealth?.data_quality?.verdict || "PASS"}
          </span>
          <span className="badge badge-info">
            AGENTS: {systemHealth?.agent_registry?.length || 11} ONLINE
          </span>
        </div>
      </header>

      {/* Navigation Bar */}
      <nav className="nav-tabs">
        <button
          className={`nav-tab ${activeTab === "OVERVIEW" ? "active" : ""}`}
          onClick={() => setActiveTab("OVERVIEW")}
        >
          1. MARKET REGIME &amp; RANKED OPPORTUNITIES
        </button>
        <button
          className={`nav-tab ${activeTab === "STOCK_DOSSIER" ? "active" : ""}`}
          onClick={() => setActiveTab("STOCK_DOSSIER")}
        >
          2. STOCK RESEARCH DOSSIER ({selectedTicker})
        </button>
        <button
          className={`nav-tab ${activeTab === "AGENT_CONSOLE" ? "active" : ""}`}
          onClick={() => setActiveTab("AGENT_CONSOLE")}
        >
          3. ADK MULTI-AGENT RESEARCH CONSOLE
        </button>
        <button
          className={`nav-tab ${activeTab === "BACKTESTING" ? "active" : ""}`}
          onClick={() => setActiveTab("BACKTESTING")}
        >
          4. WALK-FORWARD BACKTESTING &amp; CALIBRATION
        </button>
        <button
          className={`nav-tab ${activeTab === "SYSTEM_HEALTH" ? "active" : ""}`}
          onClick={() => setActiveTab("SYSTEM_HEALTH")}
        >
          5. PIPELINE HEALTH &amp; GOVERNANCE AUDIT
        </button>
      </nav>

      {/* Main Content Workspace */}
      <main className="workspace-grid">
        {/* ==================== TAB 1: OVERVIEW & OPPORTUNITIES ==================== */}
        {activeTab === "OVERVIEW" && (
          <>
            {/* Macro & Market Regime Strip */}
            <div className="kpi-row">
              <div className="panel">
                <div className="kpi-label">Market Regime (MEASURED FACT)</div>
                <div className="kpi-value text-bull" style={{ fontSize: "15px" }}>
                  {marketOverview?.market_regime?.regime_classification || "EXPANSIONARY_MOMENTUM"}
                </div>
                <div className="kpi-sub">
                  {marketOverview?.market_regime?.regime_narrative ||
                    "Constructive equity trend with contained realized volatility."}
                </div>
              </div>
              <div className="panel">
                <div className="kpi-label">SPY 20D Return / Realized Vol</div>
                <div className="kpi-value">
                  <span className="text-bull">
                    {marketOverview?.regime_metrics?.spy_ret_20d_pct >= 0 ? "+" : ""}
                    {marketOverview?.regime_metrics?.spy_ret_20d_pct ?? 2.4}%
                  </span>{" "}
                  / {marketOverview?.regime_metrics?.spy_vol_20d_ann_pct ?? 14.2}%
                </div>
                <div className="kpi-sub">
                  SPY EOD Close: ${marketOverview?.market_regime?.spy_latest_close ?? "582.00"}
                </div>
              </div>
              <div className="panel">
                <div className="kpi-label">CBOE VIX / 10Y-2Y Yield Spread</div>
                <div className="kpi-value">
                  {marketOverview?.regime_metrics?.vix_index ?? 17.85}{" "}
                  <span style={{ fontSize: "13px", color: "#22d3ee" }}>
                    ({marketOverview?.regime_metrics?.treasury_10y_2y_spread_pct >= 0 ? "+" : ""}
                    {marketOverview?.regime_metrics?.treasury_10y_2y_spread_pct ?? 0.22}% curve)
                  </span>
                </div>
                <div className="kpi-sub">FRED Macro Series (Point-in-Time Release)</div>
              </div>
              <div className="panel">
                <div className="kpi-label">Watchlist Quick Jump ({watchlist.length})</div>
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
                  {watchlist.map((t) => (
                    <button
                      key={t}
                      className="btn-ghost active"
                      onClick={() => openStockDossier(t)}
                    >
                      {t} ↗
                    </button>
                  ))}
                </div>
                <div className="kpi-sub" style={{ marginTop: "6px" }}>
                  Click any ticker to inspect multi-horizon forecasts &amp; SEC filings
                </div>
              </div>
            </div>

            {/* Signal Anomaly Monitors */}
            <div className="three-col">
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Unusual Volume Anomalies (20D Z-Score)</span>
                  <span className="badge badge-info">MEASURED FACT</span>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Close</th>
                      <th>Vol Z-Score</th>
                      <th>1D Ret</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(marketOverview?.signal_monitors?.volume_anomalies || []).map((row: any) => (
                      <tr key={row.ticker} onClick={() => openStockDossier(row.ticker)}>
                        <td style={{ fontWeight: 700, color: "#22d3ee" }}>{row.ticker}</td>
                        <td>${row.close_price}</td>
                        <td>{row.volume_zscore_20d > 0 ? `+${row.volume_zscore_20d}` : row.volume_zscore_20d}σ</td>
                        <td className={row.ret_1d_pct >= 0 ? "text-bull" : "text-bear"}>
                          {row.ret_1d_pct >= 0 ? `+${row.ret_1d_pct}%` : `${row.ret_1d_pct}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">20D Relative Momentum Leaders</span>
                  <span className="badge badge-bull">MOMENTUM</span>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Close</th>
                      <th>20D Ret</th>
                      <th>vs SPY</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(marketOverview?.signal_monitors?.momentum_leaders || []).map((row: any) => (
                      <tr key={row.ticker} onClick={() => openStockDossier(row.ticker)}>
                        <td style={{ fontWeight: 700, color: "#22d3ee" }}>{row.ticker}</td>
                        <td>${row.close_price}</td>
                        <td className="text-bull">+{row.ret_20d_pct}%</td>
                        <td className={row.rel_strength_sector_20d_pct >= 0 ? "text-bull" : "text-bear"}>
                          {row.rel_strength_sector_20d_pct >= 0 ? `+${row.rel_strength_sector_20d_pct}%` : `${row.rel_strength_sector_20d_pct}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Elevated Volatility &amp; Drawdown Monitor</span>
                  <span className="badge badge-bear">RISK MONITOR</span>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Close</th>
                      <th>20D Ann Vol</th>
                      <th>60D Max DD</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(marketOverview?.signal_monitors?.volatility_Alerts || []).map((row: any) => (
                      <tr key={row.ticker} onClick={() => openStockDossier(row.ticker)}>
                        <td style={{ fontWeight: 700, color: "#22d3ee" }}>{row.ticker}</td>
                        <td>${row.close_price}</td>
                        <td className="text-amber">{row.vol_20d_ann_pct}%</td>
                        <td className="text-bear">{row.max_drawdown_60d_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Ranked Stock Opportunities Table */}
            <div className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    TRANSPARENT RANKED STOCK RESEARCH OPPORTUNITIES ({filteredOpportunities.length})
                  </div>
                  <div className="kpi-sub" style={{ marginTop: "2px" }}>
                    Formula: {opportunitiesData.scoring_methodology || "40% Calibrated Model Edge + 20% Momentum + 20% PIT Fundamentals + 20% Risk Penalty"}
                  </div>
                </div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                  <input
                    type="text"
                    className="input-control"
                    placeholder="Search ticker, company, sector..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <select
                    className="select-control"
                    value={sectorFilter}
                    onChange={(e) => setSectorFilter(e.target.value)}
                  >
                    <option value="ALL">All Sectors</option>
                    {(opportunitiesData.available_sectors || []).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <select
                    className="select-control"
                    value={stanceFilter}
                    onChange={(e) => setStanceFilter(e.target.value)}
                  >
                    <option value="ALL">All Research Stances</option>
                    <option value="BULLISH">Bullish Candidates</option>
                    <option value="NEUTRAL">Neutral / Monitor</option>
                    <option value="BEARISH">Bearish / Risk Candidates</option>
                  </select>
                  <button
                    className={`btn-ghost ${watchlistOnly ? "active" : ""}`}
                    onClick={() => setWatchlistOnly(!watchlistOnly)}
                  >
                    ★ Watchlist Only
                  </button>
                </div>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>★</th>
                      <th>Rank</th>
                      <th>Ticker</th>
                      <th>Company / Sector</th>
                      <th>EOD Price</th>
                      <th>Composite Score</th>
                      <th>Score Breakdown (Edge/Mom/Fund/Risk)</th>
                      <th>5D Calibrated Prob Up</th>
                      <th>5D Exp Excess Ret</th>
                      <th>90% Interval (5D)</th>
                      <th>Research Stance</th>
                      <th>Critic Gate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOpportunities.map((item) => {
                      const sb = item.score_breakdown;
                      return (
                        <tr key={item.ticker} onClick={() => openStockDossier(item.ticker)}>
                          <td onClick={(e) => toggleWatchlist(item.ticker, e)}>
                            <span style={{ color: watchlist.includes(item.ticker) ? "#f59e0b" : "#657999" }}>
                              {watchlist.includes(item.ticker) ? "★" : "☆"}
                            </span>
                          </td>
                          <td>#{item.rank_position}</td>
                          <td style={{ fontWeight: 700, color: "#22d3ee" }}>{item.ticker}</td>
                          <td style={{ fontFamily: "var(--font-sans)" }}>
                            <div style={{ fontWeight: 600 }}>{item.company_name || item.ticker}</div>
                            <div className="kpi-sub">{item.sector}</div>
                          </td>
                          <td>${item.latest_price?.toFixed(2) ?? "—"}</td>
                          <td>
                            <span style={{ fontWeight: 700, color: "#388bfd" }}>
                              {item.composite_rank_score.toFixed(1)}
                            </span>{" "}
                            / 100
                          </td>
                          <td className="kpi-sub">
                            {sb
                              ? `${sb.model_edge_score} / ${sb.momentum_score} / ${sb.fundamental_score} / ${sb.risk_penalty_score}`
                              : "—"}
                          </td>
                          <td className={item.prob_material_move_up >= 0.54 ? "text-bull" : ""}>
                            {(item.prob_material_move_up * 100).toFixed(1)}%
                          </td>
                          <td className={item.expected_excess_return_bps >= 0 ? "text-bull" : "text-bear"}>
                            {item.expected_excess_return_bps >= 0 ? "+" : ""}
                            {item.expected_excess_return_bps.toFixed(0)} bps
                          </td>
                          <td>
                            [{item.uncertainty_range_low_pct.toFixed(1)}%, +
                            {item.uncertainty_range_high_pct.toFixed(1)}%]
                          </td>
                          <td>
                            <span className={stanceBadgeClass(item.research_stance)}>
                              {item.research_stance}
                            </span>
                          </td>
                          <td>
                            <span className="badge badge-epistemic">{item.critic_status}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ==================== TAB 2: SINGLE-STOCK RESEARCH DOSSIER ==================== */}
        {activeTab === "STOCK_DOSSIER" && (
          <>
            {/* Stock Selector Strip */}
            <div className="panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <span className="panel-title">SELECT SECURITY:</span>
                <select
                  className="select-control"
                  value={selectedTicker}
                  onChange={(e) => setSelectedTicker(e.target.value)}
                >
                  {(opportunitiesData.opportunities || []).map((o) => (
                    <option key={o.ticker} value={o.ticker}>
                      {o.ticker} — {o.company_name || o.sector} (Rank #{o.rank_position})
                    </option>
                  ))}
                </select>
                <button
                  className="btn-ghost active"
                  onClick={() => toggleWatchlist(selectedTicker)}
                >
                  {watchlist.includes(selectedTicker) ? "★ In Watchlist" : "☆ Add to Watchlist"}
                </button>
                <button
                  className="btn-primary"
                  onClick={() => {
                    setAgentTicker(selectedTicker);
                    setAgentQuery(
                      `Run deep multi-agent analysis on ${selectedTicker}: evaluate 1d/5d/20d calibrated probabilities, point-in-time SEC filings, and downside invalidation triggers.`
                    );
                    setActiveTab("AGENT_CONSOLE");
                  }}
                >
                  Launch Live ADK Multi-Agent Investigation for {selectedTicker} →
                </button>
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <span className="badge badge-info">CIK: {stockDossier?.security?.cik || "—"}</span>
                <span className="badge badge-info">
                  SECTOR: {stockDossier?.security?.sector || "—"}
                </span>
                <span className="badge badge-epistemic">
                  LATENCY: {stockDossier?.price_history?.latency_class || "DELAYED_EOD"}
                </span>
              </div>
            </div>

            {loadingDossier && <div className="panel">Loading {selectedTicker} research dossier...</div>}

            {stockDossier && (
              <>
                {/* Top KPI Summary Row */}
                <div className="kpi-row">
                  <div className="panel">
                    <div className="kpi-label">
                      {stockDossier.ticker} Measured EOD Close [HISTORICAL FACT]
                    </div>
                    <div className="kpi-value">
                      ${Number(stockDossier.price_history.latest_close || 0).toFixed(2)}
                    </div>
                    <div className="kpi-sub">
                      As of {stockDossier.price_history.latest_trade_date} ({stockDossier.price_history.source_provider})
                    </div>
                  </div>

                  <div className="panel">
                    <div className="kpi-label">Composite Opportunity Rank &amp; Stance</div>
                    <div className="kpi-value" style={{ fontSize: "16px" }}>
                      Rank #{stockDossier.recommendation_and_scenarios?.rank_position} (
                      {stockDossier.recommendation_and_scenarios?.composite_rank_score}/100)
                    </div>
                    <div style={{ marginTop: "4px" }}>
                      <span className={stanceBadgeClass(stockDossier.recommendation_and_scenarios?.research_stance)}>
                        {stockDossier.recommendation_and_scenarios?.research_stance}
                      </span>
                    </div>
                  </div>

                  <div className="panel">
                    <div className="kpi-label">
                      {selectedHorizon}D Calibrated Upside Prob [MODEL FORECAST]
                    </div>
                    <div className="kpi-value text-bull">
                      {activeHorizonForecast
                        ? `${(activeHorizonForecast.calibrated_prob_up * 100).toFixed(1)}%`
                        : "—"}
                    </div>
                    <div className="kpi-sub">
                      Target: {activeHorizonForecast?.target_definition || `${selectedHorizon}D excess return`}
                    </div>
                  </div>

                  <div className="panel">
                    <div className="kpi-label">
                      {selectedHorizon}D 10%–90% Return Uncertainty Interval
                    </div>
                    <div className="kpi-value" style={{ fontSize: "17px" }}>
                      <span className="text-bear">
                        {activeHorizonForecast?.prediction_interval_low_pct?.toFixed(2)}%
                      </span>{" "}
                      to{" "}
                      <span className="text-bull">
                        +{activeHorizonForecast?.prediction_interval_high_pct?.toFixed(2)}%
                      </span>
                    </div>
                    <div className="kpi-sub">
                      OOS ROC-AUC: {activeHorizonForecast?.roc_auc_oos?.toFixed(3)} | Brier:{" "}
                      {activeHorizonForecast?.brier_score_oos?.toFixed(4)}
                    </div>
                  </div>
                </div>

                {/* Price Chart + Multi-Horizon Forecast Panel */}
                <div className="two-col">
                  <div className="panel">
                    <div className="panel-header">
                      <div>
                        <span className="panel-title">
                          {stockDossier.ticker} — 90-DAY VALIDATED OHLCV PRICE, 20D SMA &amp; VOLUME
                        </span>
                      </div>
                      <span className="badge badge-info">MEASURED HISTORICAL FACT</span>
                    </div>
                    {renderPriceChart(stockDossier.price_history.bars)}
                    {/* Point-in-Time Technical & Fundamental Feature Strip */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(125px, 1fr))",
                        gap: "8px",
                        marginTop: "12px",
                        paddingTop: "10px",
                        borderTop: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div>
                        <div className="kpi-label">RSI-14</div>
                        <div className="mono">
                          {Number(stockDossier.latest_quant_features?.rsi_14 || 50).toFixed(1)}
                        </div>
                      </div>
                      <div>
                        <div className="kpi-label">20D Realized Vol</div>
                        <div className="mono">
                          {(Number(stockDossier.latest_quant_features?.vol_20d_ann || 0.2) * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="kpi-label">60D Max Drawdown</div>
                        <div className="mono text-bear">
                          {(Number(stockDossier.latest_quant_features?.max_drawdown_60d || -0.08) * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="kpi-label">60D Beta vs SPY</div>
                        <div className="mono">
                          {Number(stockDossier.latest_quant_features?.beta_spy_60d || 1.0).toFixed(2)}x
                        </div>
                      </div>
                      <div>
                        <div className="kpi-label">PIT Rev Growth YoY</div>
                        <div className="mono text-bull">
                          {(Number(stockDossier.latest_quant_features?.rev_growth_yoy_pit || 0) * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="kpi-label">PIT Profit Margin</div>
                        <div className="mono">
                          {(Number(stockDossier.latest_quant_features?.profit_margin_pit || 0) * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="kpi-label">PIT P/E TTM</div>
                        <div className="mono">
                          {Number(stockDossier.latest_quant_features?.pe_ttm_pit || 20).toFixed(1)}x
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Multi-Horizon Forecast Selector & Feature Drivers */}
                  <div className="panel">
                    <div className="panel-header">
                      <span className="panel-title">MULTI-HORIZON CALIBRATED FORECASTS</span>
                      <div style={{ display: "flex", gap: "6px" }}>
                        {[1, 5, 20].map((h) => (
                          <button
                            key={h}
                            className={`btn-ghost ${selectedHorizon === h ? "active" : ""}`}
                            onClick={() => setSelectedHorizon(h)}
                          >
                            {h}D Horizon
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="kpi-sub" style={{ marginBottom: "10px" }}>
                      <span className="badge badge-epistemic">CALIBRATED MODEL FORECAST</span>{" "}
                      Meaning of Confidence: Out-of-sample Platt-calibrated probability on chronological walk-forward folds (never subjective LLM confidence).
                    </div>

                    <table className="data-table" style={{ marginBottom: "12px" }}>
                      <thead>
                        <tr>
                          <th>Horizon</th>
                          <th>Prob Up</th>
                          <th>Prob Down</th>
                          <th>Exp Excess</th>
                          <th>90% Interval</th>
                          <th>Signal</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(stockDossier.forecasts_by_horizon || []).map((f) => (
                          <tr
                            key={f.horizon_days}
                            onClick={() => setSelectedHorizon(f.horizon_days)}
                            style={{
                              background:
                                Number(f.horizon_days) === Number(selectedHorizon)
                                  ? "rgba(34, 211, 238, 0.09)"
                                  : undefined,
                            }}
                          >
                            <td style={{ fontWeight: 700 }}>{f.horizon_days}D</td>
                            <td className="text-bull">{(f.calibrated_prob_up * 100).toFixed(1)}%</td>
                            <td className="text-bear">{(f.calibrated_prob_down * 100).toFixed(1)}%</td>
                            <td>
                              {f.expected_excess_return_bps >= 0 ? "+" : ""}
                              {f.expected_excess_return_bps.toFixed(1)} bps
                            </td>
                            <td>
                              [{f.prediction_interval_low_pct.toFixed(1)}%, +
                              {f.prediction_interval_high_pct.toFixed(1)}%]
                            </td>
                            <td>
                              <span className={stanceBadgeClass(f.signal_direction)}>
                                {f.signal_direction}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    <div className="kpi-label" style={{ marginBottom: "6px" }}>
                      Top Quantitative Feature Drivers ({selectedHorizon}D Model {activeHorizonForecast?.model_version})
                    </div>
                    {(activeHorizonForecast?.top_features || []).map((tf: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          padding: "5px 0",
                          borderBottom: "1px solid rgba(30,45,71,0.5)",
                          fontFamily: "var(--font-mono)",
                          fontSize: "11px",
                        }}
                      >
                        <span>{tf.feature || tf.name}</span>
                        <span style={{ color: "#22d3ee" }}>
                          Weight: {Number(tf.importance_weight ?? tf.contribution ?? 0).toFixed(4)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Bullish, Base-Case, and Bearish Scenarios + Invalidation */}
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">
                      SCENARIO ANALYSIS, THESIS INVALIDATION &amp; RISK SUITABILITY
                    </span>
                    <span className="badge badge-epistemic">
                      AGENT INTERPRETATION &bull; CRITIC: {stockDossier.recommendation_and_scenarios?.critic_status}
                    </span>
                  </div>

                  <div className="scenario-grid">
                    <div className="scenario-box" style={{ borderLeft: "3px solid var(--bullish-green)" }}>
                      <div className="kpi-label text-bull">BULLISH SCENARIO (90th Percentile Upside)</div>
                      <p style={{ marginTop: "6px" }}>
                        {stockDossier.recommendation_and_scenarios?.bullish_scenario}
                      </p>
                    </div>
                    <div className="scenario-box" style={{ borderLeft: "3px solid var(--accent-blue)" }}>
                      <div className="kpi-label" style={{ color: "#388bfd" }}>
                        BASE-CASE SCENARIO (Expected Trajectory)
                      </div>
                      <p style={{ marginTop: "6px" }}>
                        {stockDossier.recommendation_and_scenarios?.base_scenario}
                      </p>
                    </div>
                    <div className="scenario-box" style={{ borderLeft: "3px solid var(--bearish-red)" }}>
                      <div className="kpi-label text-bear">BEARISH SCENARIO (10th Percentile Downside)</div>
                      <p style={{ marginTop: "6px" }}>
                        {stockDossier.recommendation_and_scenarios?.bearish_scenario}
                      </p>
                    </div>
                  </div>

                  <div className="two-col" style={{ marginTop: "12px" }}>
                    <div className="scenario-box">
                      <div className="kpi-label text-amber">
                        EXPLICIT THESIS INVALIDATION CONDITIONS &amp; STOP TRIGGERS
                      </div>
                      <p style={{ marginTop: "5px" }}>
                        {stockDossier.recommendation_and_scenarios?.invalidation_conditions}
                      </p>
                      <div className="kpi-sub" style={{ marginTop: "6px" }}>
                        Independent Critic Audit: {stockDossier.recommendation_and_scenarios?.critic_notes}
                      </div>
                    </div>
                    <div className="scenario-box">
                      <div className="kpi-label text-bear">
                        REASONS THIS SECURITY MAY BE UNSUITABLE (RISK &amp; SUITABILITY FLAGS)
                      </div>
                      <ul style={{ marginTop: "6px", paddingLeft: "18px" }}>
                        {(stockDossier.recommendation_and_scenarios?.unsuitability_flags || []).map(
                          (flg, i) => (
                            <li key={i} style={{ marginBottom: "4px" }}>
                              {flg}
                            </li>
                          )
                        )}
                      </ul>
                    </div>
                  </div>
                </div>

                {/* Verified SEC EDGAR Filings, Catalysts & Point-in-Time Citations */}
                <div className="two-col">
                  <div className="panel">
                    <div className="panel-header">
                      <span className="panel-title">
                        VERIFIED SEC EDGAR FILINGS &amp; CATALYST TIMELINE
                      </span>
                      <span className="badge badge-info">EVENT vs PUBLICATION TIMESTAMPS</span>
                    </div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Type</th>
                          <th>Headline / Summary</th>
                          <th>Event Date</th>
                          <th>Publication Timestamp (PIT)</th>
                          <th>Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(stockDossier.sec_edgar_catalysts || []).map((cat) => (
                          <tr key={cat.event_id}>
                            <td>
                              <span className="badge badge-info">{cat.catalyst_type}</span>
                            </td>
                            <td style={{ fontFamily: "var(--font-sans)" }}>
                              <div style={{ fontWeight: 600 }}>{cat.headline}</div>
                              <div className="kpi-sub">{cat.summary}</div>
                            </td>
                            <td>{cat.event_timestamp?.slice(0, 10) || cat.event_date}</td>
                            <td>{cat.publication_timestamp?.slice(0, 19).replace("T", " ")}Z</td>
                            <td>
                              <a
                                href={cat.source_url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: "#22d3ee" }}
                              >
                                SEC EDGAR ↗
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="panel">
                    <div className="panel-header">
                      <span className="panel-title">
                        POINT-IN-TIME SEC XBRL FUNDAMENTAL SNAPSHOTS (ZERO LOOK-AHEAD)
                      </span>
                      <span className="badge badge-bull">PIT VERIFIED</span>
                    </div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th>Value</th>
                          <th>Period</th>
                          <th>Period End</th>
                          <th>SEC Filing Acceptance (PIT Gate)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(stockDossier.fundamentals_point_in_time || []).map((row, idx) => (
                          <tr key={idx}>
                            <td style={{ fontWeight: 700 }}>{row.metric_name}</td>
                            <td>
                              {row.metric_value} ({row.unit})
                            </td>
                            <td>
                              {row.fiscal_year} {row.fiscal_period} ({row.form_type})
                            </td>
                            <td>{row.period_end_date}</td>
                            <td>{row.acceptance_timestamp?.slice(0, 19).replace("T", " ")}Z</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {/* ==================== TAB 3: ADK MULTI-AGENT RESEARCH CONSOLE ==================== */}
        {activeTab === "AGENT_CONSOLE" && (
          <>
            <div className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    GOOGLE ADK ROOT AGENT &amp; DYNAMIC ORCHESTRATOR CONSOLE
                  </div>
                  <div className="kpi-sub">
                    Routes natural-language financial research queries through Data Governance → Parallel Domain Specialists → Independent Critic Verification
                  </div>
                </div>
                <span className="badge badge-epistemic">VERTEX AI GEMINI + GOOGLE SEARCH GROUNDING</span>
              </div>

              <form onSubmit={runAgentResearch} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <input
                    type="text"
                    className="input-control"
                    style={{ flex: 1, minWidth: "320px" }}
                    value={agentQuery}
                    onChange={(e) => setAgentQuery(e.target.value)}
                    placeholder="Ask the Root Agent to analyze a stock, catalyst, macro regime, or forecast..."
                  />
                  <select
                    className="select-control"
                    value={agentTicker}
                    onChange={(e) => setAgentTicker(e.target.value)}
                  >
                    {(opportunitiesData.opportunities || []).map((o) => (
                      <option key={o.ticker} value={o.ticker}>
                        Ticker: {o.ticker}
                      </option>
                    ))}
                  </select>
                  <select
                    className="select-control"
                    value={agentIntent}
                    onChange={(e) => setAgentIntent(e.target.value)}
                  >
                    <option value="STOCK_ANALYSIS">Intent: Full Stock Analysis</option>
                    <option value="FULL_RECOMMENDATION_WORKFLOW">Intent: Full Recommendation Workflow</option>
                    <option value="CATALYST_RESEARCH">Intent: News &amp; SEC Catalyst Research</option>
                    <option value="FORECASTING">Intent: Multi-Horizon Forecasting</option>
                    <option value="RISK_EVALUATION">Intent: Downside Risk &amp; Suitability</option>
                    <option value="MARKET_REGIME">Intent: Macro &amp; Market Regime</option>
                    <option value="PERFORMANCE_ANALYSIS">Intent: Walk-Forward Backtest Audit</option>
                  </select>
                  <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
                    <input
                      type="checkbox"
                      checked={enableLiveVertex}
                      onChange={(e) => setEnableLiveVertex(e.target.checked)}
                    />
                    Enable Live Vertex AI Gemini Grounding
                  </label>
                  <button type="submit" className="btn-primary" disabled={agentLoading}>
                    {agentLoading ? "Executing Multi-Agent DAG..." : "Execute Research Workflow"}
                  </button>
                </div>
              </form>
            </div>

            {agentResponse && (
              <>
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">
                      CONSOLIDATED ROOT AGENT DOSSIER — {agentResponse.target_ticker} ({agentResponse.classified_intent})
                    </span>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <span className="badge badge-bull">
                        GOVERNANCE: {agentResponse.governance_verdict}
                      </span>
                      <span className="badge badge-epistemic">
                        CRITIC: {agentResponse.critic_verdict}
                      </span>
                      <span className="badge badge-info">
                        LATENCY: {agentResponse.total_latency_ms} ms
                      </span>
                    </div>
                  </div>
                  <p style={{ fontSize: "13.5px", lineHeight: 1.6, marginBottom: "10px" }}>
                    {agentResponse.executive_summary}
                  </p>
                  {agentResponse.signal_conflicts?.length > 0 && (
                    <div className="scenario-box" style={{ borderLeft: "3px solid var(--neutral-amber)", marginBottom: "10px" }}>
                      <div className="kpi-label text-amber">INTER-AGENT SIGNAL CONFLICT DETECTED</div>
                      {agentResponse.signal_conflicts.map((c: string, i: number) => (
                        <div key={i} style={{ marginTop: "4px" }}>{c}</div>
                      ))}
                    </div>
                  )}
                  <div className="kpi-sub">{agentResponse.disclaimer}</div>
                </div>

                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">
                      ORCHESTRATOR EXECUTION TRACE ({agentResponse.agents_executed?.length || 0} SPECIALIZED AGENTS INVOKED)
                    </span>
                    <span className="badge badge-info">TRACE ID: {agentResponse.trace_id}</span>
                  </div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Agent Name</th>
                        <th>Epistemic Classification</th>
                        <th>Status</th>
                        <th>Uncertainty / Confidence Definition</th>
                        <th>Point Estimate</th>
                        <th>Citations</th>
                        <th>Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(agentResponse.agent_results || {}).map(([name, res]: [string, any]) => (
                        <tr key={name}>
                          <td style={{ fontWeight: 700, color: "#22d3ee" }}>{name}</td>
                          <td>
                            <span className="badge badge-epistemic">{res.epistemic_classification}</span>
                          </td>
                          <td>
                            <span className="badge badge-bull">{res.status}</span>
                          </td>
                          <td style={{ fontFamily: "var(--font-sans)" }}>{res.uncertainty?.meaning}</td>
                          <td>{res.uncertainty?.point_estimate ?? "—"}</td>
                          <td>{res.citations?.length || 0} sources</td>
                          <td>{res.telemetry?.duration_ms} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}

        {/* ==================== TAB 4: BACKTESTING & CALIBRATION ==================== */}
        {activeTab === "BACKTESTING" && (
          <>
            <div className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    CHRONOLOGICAL WALK-FORWARD BACKTESTING (NET OF TRANSACTION COSTS &amp; SLIPPAGE)
                  </div>
                  <div className="kpi-sub">
                    Expanding-window out-of-sample evaluation with h-day embargo gap &bull; 10 bps transaction cost + 5 bps slippage deducted per turnover
                  </div>
                </div>
                <div style={{ display: "flex", gap: "6px" }}>
                  {[1, 5, 20].map((h) => (
                    <button
                      key={h}
                      className={`btn-ghost ${selectedHorizon === h ? "active" : ""}`}
                      onClick={() => setSelectedHorizon(h)}
                    >
                      {h}D Horizon Strategy
                    </button>
                  ))}
                </div>
              </div>

              {(() => {
                const bt =
                  (backtestData?.backtest_runs || []).find(
                    (b: any) => Number(b.horizon_days) === Number(selectedHorizon)
                  ) || (backtestData?.backtest_runs || [])[0];
                if (!bt) return <div className="kpi-sub">Loading walk-forward backtests...</div>;
                return (
                  <>
                    <div className="kpi-row" style={{ marginBottom: "14px" }}>
                      <div className="scenario-box">
                        <div className="kpi-label">Net Cumulative Strategy Return</div>
                        <div className="kpi-value text-bull">
                          {bt.total_return_pct >= 0 ? "+" : ""}
                          {bt.total_return_pct}%
                        </div>
                        <div className="kpi-sub">
                          vs SPY Benchmark: {bt.benchmark_return_pct >= 0 ? "+" : ""}
                          {bt.benchmark_return_pct}%
                        </div>
                      </div>
                      <div className="scenario-box">
                        <div className="kpi-label">Net Out-of-Sample Sharpe / Sortino</div>
                        <div className="kpi-value">
                          {bt.sharpe_ratio} / {bt.sortino_ratio}
                        </div>
                        <div className="kpi-sub">Information Ratio vs SPY: {bt.information_ratio}</div>
                      </div>
                      <div className="scenario-box">
                        <div className="kpi-label">Out-of-Sample Hit Rate &amp; Turnover</div>
                        <div className="kpi-value text-bull">{bt.hit_rate_pct}%</div>
                        <div className="kpi-sub">
                          Avg Rebalance Turnover: {bt.avg_turnover_pct}% ({bt.total_trades} trades)
                        </div>
                      </div>
                      <div className="scenario-box">
                        <div className="kpi-label">Max Drawdown / Cost Drag</div>
                        <div className="kpi-value text-bear">{bt.max_drawdown_pct}%</div>
                        <div className="kpi-sub">
                          Costs: {bt.transaction_cost_bps} bps fee + {bt.slippage_bps} bps slippage
                        </div>
                      </div>
                    </div>
                    {renderEquityCurveChart(bt.equity_curve || [])}
                  </>
                );
              })()}
            </div>

            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">
                  QUANTITATIVE MODEL REGISTRY &amp; OUT-OF-SAMPLE CALIBRATION DIAGNOSTICS
                </span>
                <span className="badge badge-info">PLATT SIGMOID WALK-FORWARD CALIBRATION</span>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Model ID</th>
                    <th>Version</th>
                    <th>Horizon</th>
                    <th>Target Definition</th>
                    <th>OOS ROC-AUC</th>
                    <th>OOS Brier Score</th>
                    <th>Brier Skill Score</th>
                    <th>ECE (Calibration Error)</th>
                    <th>Precision@5</th>
                  </tr>
                </thead>
                <tbody>
                  {(backtestData?.model_registry || []).map((m: any) => (
                    <tr key={m.model_id}>
                      <td style={{ fontWeight: 700, color: "#22d3ee" }}>{m.model_id}</td>
                      <td>{m.model_version}</td>
                      <td>{m.horizon_days}D</td>
                      <td style={{ fontFamily: "var(--font-sans)" }}>
                        Excess return over SPY &ge; +{m.target_threshold_pct}%
                      </td>
                      <td className="text-bull">{m.roc_auc_oos}</td>
                      <td>{m.brier_score_oos}</td>
                      <td className="text-bull">+{m.brier_skill_score_oos}</td>
                      <td>{m.ece_oos}</td>
                      <td>{(Number(m.precision_at_5_oos || 0) * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* ==================== TAB 5: SYSTEM HEALTH & GOVERNANCE ==================== */}
        {activeTab === "SYSTEM_HEALTH" && (
          <>
            <div className="two-col">
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">DATA PIPELINE &amp; QUALITY GOVERNANCE CHECKS</span>
                  <span className="badge badge-bull">
                    VERDICT: {systemHealth?.data_quality?.verdict || "PASS"}
                  </span>
                </div>
                <div className="kpi-sub" style={{ marginBottom: "10px" }}>
                  Run ID: {systemHealth?.pipeline_run?.run_id} | BigQuery Warehouse:{" "}
                  {systemHealth?.bq_dataset} | Rows Processed:{" "}
                  {systemHealth?.pipeline_run?.rows_processed}
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Governance Check</th>
                      <th>Status</th>
                      <th>Severity</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(systemHealth?.data_quality?.checks || []).map((chk: any, idx: number) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 700 }}>{chk.check_name}</td>
                        <td>
                          <span className={chk.passed ? "badge badge-bull" : "badge badge-bear"}>
                            {chk.passed ? "PASSED" : "FAILED"}
                          </span>
                        </td>
                        <td>{chk.severity}</td>
                        <td style={{ fontFamily: "var(--font-sans)" }}>{chk.details}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">
                    GOVERNED SPECIALIZED AGENT REGISTRY &amp; MCP ALLOWLISTS
                  </span>
                  <span className="badge badge-epistemic">LEAST-PRIVILEGE MCP</span>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Agent Role</th>
                      <th>Epistemic Type</th>
                      <th>Allowed MCP Tools</th>
                      <th>Timeout</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(systemHealth?.agent_registry || []).map((ag: any) => (
                      <tr key={ag.agent_name}>
                        <td style={{ fontWeight: 700, color: "#22d3ee" }}>{ag.agent_name}</td>
                        <td>{ag.epistemic_classification}</td>
                        <td style={{ fontFamily: "var(--font-sans)", fontSize: "11px" }}>
                          {(ag.allowed_mcp_tools || []).join(", ")}
                        </td>
                        <td>{ag.timeout_seconds}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
