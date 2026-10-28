"""Controlled MCP Tool Server for Market Data, OHLCV History, and Macro Indicators (`mcp.market_data.server`)."""

import json
from pathlib import Path
import re
from typing import Any, Dict, List
from data.ingestion.universe import SECURITY_MASTER_UNIVERSE, TICKER_TO_SECURITY
from mcp.security import enforce_agent_tool_permission


SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "latest_snapshot.json"
TICKER_REGEX = re.compile(r"^[A-Z]{1,5}$")


class MarketDataMCPServer:
    """Controlled MCP Tool Server for OHLCV bars, Security Master, and Macro Indicators."""

    def _load_snapshot(self) -> Dict[str, Any]:
        if not SNAPSHOT_PATH.exists():
            from data.ingestion.pipeline import execute_pipeline
            execute_pipeline(mode="incremental", upload_to_bq=False)
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_ticker_universe(self, caller_agent: str, ticker: str) -> Dict[str, Any]:
        """Validate ticker format and check coverage in the governed Security Master universe."""
        enforce_agent_tool_permission(caller_agent, "validate_ticker_universe")
        cleaned = (ticker or "").strip().upper()
        if not TICKER_REGEX.match(cleaned):
            return {
                "tool": "mcp.market_data.validate_ticker_universe",
                "valid_format": False,
                "in_universe": False,
                "ticker": cleaned,
                "error": "Ticker must be 1-5 uppercase ASCII letters.",
            }
        sec = TICKER_TO_SECURITY.get(cleaned)
        return {
            "tool": "mcp.market_data.validate_ticker_universe",
            "valid_format": True,
            "in_universe": sec is not None,
            "ticker": cleaned,
            "security": sec,
            "supported_tickers": [s["ticker"] for s in SECURITY_MASTER_UNIVERSE if not s["is_etf"]],
        }

    def get_security_metadata(self, caller_agent: str, ticker: str) -> Dict[str, Any]:
        """Return point-in-time Security Master record (CIK, sector, industry, benchmark)."""
        enforce_agent_tool_permission(caller_agent, "get_security_metadata")
        cleaned = (ticker or "").strip().upper()
        sec = TICKER_TO_SECURITY.get(cleaned)
        if not sec:
            raise ValueError(f"Ticker '{cleaned}' is not in the governed Security Master universe.")
        return {
            "tool": "mcp.market_data.get_security_metadata",
            "caller_agent": caller_agent,
            "security": sec,
        }

    def get_ohlcv_history(
        self, caller_agent: str, ticker: str, limit_days: int = 60
    ) -> Dict[str, Any]:
        """Return validated daily OHLCV bars with provenance and latency badge."""
        enforce_agent_tool_permission(caller_agent, "get_ohlcv_history")
        cleaned = (ticker or "").strip().upper()
        snap = self._load_snapshot()
        bars: List[Dict[str, Any]] = [
            b for b in snap.get("recent_ohlcv", []) if b.get("ticker") == cleaned
        ]
        bars.sort(key=lambda x: x.get("trade_date", ""))
        sliced = bars[-max(5, min(limit_days, 90)) :]
        latest_bar = sliced[-1] if sliced else {}
        return {
            "tool": "mcp.market_data.get_ohlcv_history",
            "caller_agent": caller_agent,
            "ticker": cleaned,
            "bar_count": len(sliced),
            "latest_trade_date": latest_bar.get("trade_date"),
            "latest_close": latest_bar.get("close", latest_bar.get("close_price")),
            "source_provider": latest_bar.get("source_provider", "yahoo_finance_v8_eod"),
            "latency_class": "DELAYED_EOD",
            "bars": sliced,
        }

    def get_macro_regime_snapshot(self, caller_agent: str) -> Dict[str, Any]:
        """Return latest macroeconomic indicators (VIX, 10Y-2Y curve, Fed Funds, CPI, HY spread) and benchmark ETFs."""
        enforce_agent_tool_permission(caller_agent, "get_macro_regime_snapshot")
        snap = self._load_snapshot()
        macros = snap.get("macro_indicators", [])
        etf_tickers = {"SPY", "QQQ", "XLK", "XLF", "XLV"}
        etf_features = [
            f for f in snap.get("latest_features", []) if f.get("ticker") in etf_tickers
        ]
        return {
            "tool": "mcp.market_data.get_macro_regime_snapshot",
            "caller_agent": caller_agent,
            "generated_at": snap.get("generated_at"),
            "macro_indicators": macros,
            "benchmark_etf_features": etf_features,
        }


market_data_mcp_server = MarketDataMCPServer()
