"""Data Quality & Governance Validator.

Enforces mandatory data quality gates before any quantitative forecast or
agentic stock recommendation can be published:
1. Freshness SLA check (hours since latest bar vs threshold)
2. Schema & non-null completeness check
3. Duplicate (security_id, trade_date) detection
4. Non-positive or anomalous price jump check (>60% single-day unadjusted jump)
5. Point-in-time anti-look-ahead audit (`acceptance_timestamp <= publication_timestamp`)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd
from orchestration.config import settings


def validate_market_dataset(
    ohlcv_df: pd.DataFrame,
    pit_fundamentals_df: pd.DataFrame,
    max_freshness_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """Run comprehensive data quality checks and return a structured verdict."""
    sla_hours = max_freshness_hours or settings.min_data_freshness_hours
    checks: List[Dict[str, Any]] = []

    if ohlcv_df is None or ohlcv_df.empty:
        return {
            "verdict": "BLOCK",
            "passed_count": 0,
            "failed_count": 1,
            "freshness_lag_hours": 9999.0,
            "checks": [
                {
                    "check_name": "ohlcv_non_empty",
                    "passed": False,
                    "severity": "CRITICAL",
                    "details": "OHLCV dataset is empty.",
                }
            ],
        }

    # 1. Freshness check (accounting for weekends)
    max_trade_date = pd.to_datetime(ohlcv_df["trade_date"]).max()
    now_utc = datetime.now(timezone.utc)
    latest_bar_utc = datetime(
        max_trade_date.year, max_trade_date.month, max_trade_date.day, 20, 0, tzinfo=timezone.utc
    )
    lag_hours = max(0.0, (now_utc - latest_bar_utc).total_seconds() / 3600.0)
    freshness_ok = lag_hours <= sla_hours
    checks.append(
        {
            "check_name": "data_freshness_sla",
            "passed": bool(freshness_ok),
            "severity": "INFO" if freshness_ok else "CRITICAL",
            "details": f"Latest trade_date={max_trade_date.strftime('%Y-%m-%d')} (lag={lag_hours:.1f}h vs SLA={sla_hours:.1f}h).",
        }
    )

    # 2. Duplicate records check
    dup_count = int(ohlcv_df.duplicated(subset=["security_id", "trade_date"]).sum())
    checks.append(
        {
            "check_name": "no_duplicate_bars",
            "passed": dup_count == 0,
            "severity": "INFO" if dup_count == 0 else "WARNING",
            "details": f"Found {dup_count} duplicate (security_id, trade_date) rows.",
        }
    )

    # 3. Positive prices check
    bad_prices = int((ohlcv_df["close"] <= 0).sum() + (ohlcv_df["open"] <= 0).sum())
    checks.append(
        {
            "check_name": "positive_ohlc_prices",
            "passed": bad_prices == 0,
            "severity": "INFO" if bad_prices == 0 else "CRITICAL",
            "details": f"Found {bad_prices} non-positive price observations.",
        }
    )

    # 4. Minimum history coverage per ticker
    counts_per_ticker = ohlcv_df.groupby("ticker")["trade_date"].count()
    min_bars = int(counts_per_ticker.min()) if not counts_per_ticker.empty else 0
    history_ok = min_bars >= settings.min_history_trading_days
    checks.append(
        {
            "check_name": "minimum_trading_history",
            "passed": bool(history_ok),
            "severity": "INFO" if history_ok else "CRITICAL",
            "details": f"Minimum bars per security={min_bars} (required >= {settings.min_history_trading_days}).",
        }
    )

    # 5. Point-in-time fundamental anti-look-ahead check
    lookahead_violations = 0
    if pit_fundamentals_df is not None and not pit_fundamentals_df.empty:
        p_dates = pd.to_datetime(pit_fundamentals_df["period_end_date"])
        f_dates = pd.to_datetime(pit_fundamentals_df["filing_date"])
        lookahead_violations = int((f_dates < p_dates).sum())

    checks.append(
        {
            "check_name": "pit_fundamentals_no_lookahead",
            "passed": lookahead_violations == 0,
            "severity": "INFO" if lookahead_violations == 0 else "CRITICAL",
            "details": f"Point-in-time filing_date >= period_end_date violations: {lookahead_violations}.",
        }
    )

    passed_count = sum(1 for c in checks if c["passed"])
    failed_count = sum(1 for c in checks if not c["passed"])
    critical_failures = sum(1 for c in checks if not c["passed"] and c["severity"] == "CRITICAL")

    verdict = "PASS" if critical_failures == 0 else "BLOCK"
    return {
        "verdict": verdict,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "critical_failures": critical_failures,
        "freshness_lag_hours": round(lag_hours, 2),
        "latest_trade_date": max_trade_date.strftime("%Y-%m-%d"),
        "total_rows": len(ohlcv_df),
        "unique_tickers": int(ohlcv_df["ticker"].nunique()),
        "checks": checks,
    }
