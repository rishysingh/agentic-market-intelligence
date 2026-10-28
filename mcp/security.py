"""MCP Security Guardrails: Per-Agent Tool Allowlists, Read-Only SQL Enforcement,
and Prompt-Injection Sanitization (`mcp.security`).
"""

import re
from typing import Dict, Set


class MCPPermissionError(PermissionError):
    """Raised when an agent attempts to invoke an unauthorized MCP tool."""


class MCPSqlSafetyError(ValueError):
    """Raised when a SQL statement violates read-only or dataset scoping rules."""


# Explicit Per-Agent Tool Allowlist (Least Privilege by Agent Role)
AGENT_TOOL_ALLOWLIST: Dict[str, Set[str]] = {
    "root_agent": {
        "get_pipeline_and_dq_health",
        "validate_ticker_universe",
    },
    "orchestrator_agent": {
        "get_pipeline_and_dq_health",
        "validate_ticker_universe",
        "get_latest_recommendations",
    },
    "market_regime_agent": {
        "get_macro_regime_snapshot",
        "get_ohlcv_history",
        "get_security_features_and_forecasts",
    },
    "market_data_agent": {
        "get_ohlcv_history",
        "get_security_metadata",
        "validate_ticker_universe",
        "get_pipeline_and_dq_health",
    },
    "news_catalyst_agent": {
        "get_sec_edgar_catalysts_and_fundamentals",
        "run_grounded_news_search",
        "get_security_metadata",
    },
    "quantitative_agent": {
        "get_security_features_and_forecasts",
        "get_ohlcv_history",
        "execute_approved_query",
    },
    "forecasting_agent": {
        "get_security_features_and_forecasts",
        "get_model_registry_metrics",
    },
    "fundamental_agent": {
        "get_sec_edgar_catalysts_and_fundamentals",
        "get_security_features_and_forecasts",
        "get_security_metadata",
    },
    "risk_agent": {
        "get_security_features_and_forecasts",
        "get_ohlcv_history",
        "get_macro_regime_snapshot",
    },
    "critic_agent": {
        "get_security_features_and_forecasts",
        "get_sec_edgar_catalysts_and_fundamentals",
        "get_pipeline_and_dq_health",
        "get_model_registry_metrics",
    },
    "recommendation_agent": {
        "get_latest_recommendations",
        "get_security_features_and_forecasts",
        "get_sec_edgar_catalysts_and_fundamentals",
    },
    "performance_agent": {
        "get_backtest_metrics",
        "get_model_registry_metrics",
        "execute_approved_query",
    },
    "data_governance_agent": {
        "get_pipeline_and_dq_health",
        "validate_ticker_universe",
    },
}

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE|CALL|EXECUTE|EXPORT)\b",
    re.IGNORECASE,
)

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"<\s*\|\s*im_start\s*\|\s*>", re.IGNORECASE),
    re.compile(r"override\s+risk\s+controls", re.IGNORECASE),
    re.compile(r"bypass\s+critic", re.IGNORECASE),
]


def enforce_agent_tool_permission(caller_agent: str, tool_name: str) -> None:
    """Verify that `caller_agent` is explicitly permitted to invoke `tool_name`."""
    allowed = AGENT_TOOL_ALLOWLIST.get(caller_agent)
    if allowed is None:
        raise MCPPermissionError(
            f"Unknown agent role '{caller_agent}' is not registered in AGENT_TOOL_ALLOWLIST."
        )
    if tool_name not in allowed:
        raise MCPPermissionError(
            f"Agent '{caller_agent}' is not authorized to invoke MCP tool '{tool_name}'. "
            f"Allowed tools: {sorted(allowed)}"
        )


def validate_readonly_sql(sql_query: str) -> str:
    """Ensure SQL statement is strictly a single SELECT query with no DDL/DML keywords."""
    cleaned = sql_query.strip()
    if not cleaned:
        raise MCPSqlSafetyError("Empty SQL query is not permitted.")

    # Reject multiple statements separated by semicolon
    stripped_semi = cleaned.rstrip(";").strip()
    if ";" in stripped_semi:
        raise MCPSqlSafetyError("Multiple SQL statements (semicolon chaining) are prohibited.")

    if not stripped_semi.upper().startswith(("SELECT", "WITH")):
        raise MCPSqlSafetyError("Only read-only SELECT / WITH queries are permitted.")

    match = FORBIDDEN_SQL_PATTERN.search(stripped_semi)
    if match:
        raise MCPSqlSafetyError(
            f"Forbidden DDL/DML keyword '{match.group(1)}' detected in read-only BigQuery MCP tool."
        )
    return stripped_semi


def sanitize_external_text(raw_text: str, max_length: int = 2000) -> str:
    """Strip prompt-injection payloads and control characters from external news/filings."""
    if not raw_text:
        return ""
    sanitized = raw_text
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[REDACTED_ADVERSARIAL_DIRECTIVE]", sanitized)
    # Remove non-printable control chars except newline/tab
    sanitized = "".join(ch for ch in sanitized if ch.isprintable() or ch in ("\n", "\t"))
    return sanitized[:max_length]
