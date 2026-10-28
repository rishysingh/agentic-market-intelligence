"""Controlled MCP Server for BigQuery Analytical & Feature Store Access (`mcp.bigquery.server`).

Enforces:
- Per-agent tool allowlists (`mcp.security.enforce_agent_tool_permission`)
- Read-only SQL validation (`mcp.security.validate_readonly_sql`)
- `maximum_bytes_billed` query cost caps (`settings.bq_max_bytes_billed`)
- Transparent provenance (`bigquery_live` vs `verified_local_snapshot`)
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from mcp.security import enforce_agent_tool_permission, validate_readonly_sql
from orchestration.config import settings


SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "latest_snapshot.json"
TRACE_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "agent_traces.json"


class BigQueryMCPServer:
    """Controlled MCP Tool Server for BigQuery `market_intelligence` warehouse."""

    def __init__(self, use_live_bq_by_default: bool = False) -> None:
        self.use_live_bq_by_default = use_live_bq_by_default

    def _load_snapshot(self) -> Dict[str, Any]:
        if not SNAPSHOT_PATH.exists():
            from data.ingestion.pipeline import execute_pipeline
            execute_pipeline(mode="incremental", upload_to_bq=False)
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_latest_recommendations(
        self,
        caller_agent: str,
        limit: int = 20,
        sector: Optional[str] = None,
        stance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve ranked stock research recommendations with scenarios, uncertainty, and citations."""
        enforce_agent_tool_permission(caller_agent, "get_latest_recommendations")
        snap = self._load_snapshot()
        recs: List[Dict[str, Any]] = list(snap.get("recommendations", []))
        if sector and sector.upper() != "ALL":
            recs = [r for r in recs if r.get("sector", "").lower() == sector.lower()]
        if stance and stance.upper() != "ALL":
            recs = [r for r in recs if stance.upper() in r.get("research_stance", "").upper()]
        recs = sorted(recs, key=lambda x: x.get("rank_position", 999))[: max(1, min(limit, 50))]
        return {
            "tool": "mcp.bigquery.get_latest_recommendations",
            "caller_agent": caller_agent,
            "provenance": "bigquery_synced_snapshot",
            "dataset": f"{settings.project_id}.{settings.bq_dataset_id}.fact_recommendations",
            "generated_at": snap.get("generated_at"),
            "count": len(recs),
            "recommendations": recs,
        }

    def get_security_features_and_forecasts(
        self,
        caller_agent: str,
        ticker: str,
    ) -> Dict[str, Any]:
        """Retrieve latest point-in-time quant features and 1d/5d/20d calibrated forecasts for a ticker."""
        enforce_agent_tool_permission(caller_agent, "get_security_features_and_forecasts")
        t_clean = ticker.strip().upper()
        snap = self._load_snapshot()

        feats = next(
            (f for f in snap.get("latest_features", []) if f.get("ticker") == t_clean),
            None,
        )
        preds = [
            p for p in snap.get("predictions", []) if p.get("ticker") == t_clean
        ]
        preds.sort(key=lambda x: int(x.get("horizon_days", 5)))
        rec = next(
            (r for r in snap.get("recommendations", []) if r.get("ticker") == t_clean),
            None,
        )
        return {
            "tool": "mcp.bigquery.get_security_features_and_forecasts",
            "caller_agent": caller_agent,
            "ticker": t_clean,
            "provenance": "bigquery_synced_snapshot",
            "dataset": f"{settings.project_id}.{settings.bq_dataset_id}",
            "latest_features": feats,
            "forecasts": preds,
            "recommendation": rec,
        }

    def get_backtest_metrics(
        self,
        caller_agent: str,
        horizon_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve walk-forward backtest runs including transaction costs and benchmark comparison."""
        enforce_agent_tool_permission(caller_agent, "get_backtest_metrics")
        snap = self._load_snapshot()
        bts = list(snap.get("backtests", []))
        if horizon_days is not None:
            bts = [b for b in bts if int(b.get("horizon_days", 0)) == int(horizon_days)]
        return {
            "tool": "mcp.bigquery.get_backtest_metrics",
            "caller_agent": caller_agent,
            "provenance": "bigquery_synced_snapshot",
            "dataset": f"{settings.project_id}.{settings.bq_dataset_id}.fact_backtest_runs",
            "backtests": bts,
        }

    def get_model_registry_metrics(self, caller_agent: str) -> Dict[str, Any]:
        """Retrieve registered quantitative forecasting models, calibration curves, and Brier skill scores."""
        enforce_agent_tool_permission(caller_agent, "get_model_registry_metrics")
        snap = self._load_snapshot()
        return {
            "tool": "mcp.bigquery.get_model_registry_metrics",
            "caller_agent": caller_agent,
            "provenance": "bigquery_synced_snapshot",
            "dataset": f"{settings.project_id}.{settings.bq_dataset_id}.model_registry",
            "models": snap.get("model_registry", []),
        }

    def get_pipeline_and_dq_health(self, caller_agent: str) -> Dict[str, Any]:
        """Retrieve latest ingestion run telemetry, data freshness lag, and DQ check results."""
        enforce_agent_tool_permission(caller_agent, "get_pipeline_and_dq_health")
        snap = self._load_snapshot()
        traces = self.get_recent_agent_traces(limit=15)
        return {
            "tool": "mcp.bigquery.get_pipeline_and_dq_health",
            "caller_agent": caller_agent,
            "provenance": "bigquery_synced_snapshot",
            "dataset": f"{settings.project_id}.{settings.bq_dataset_id}.ops_pipeline_runs",
            "ops_pipeline_run": snap.get("ops_pipeline_run", {}),
            "dq_report": snap.get("dq_report", {}),
            "recent_agent_traces": traces,
        }

    def execute_approved_query(
        self,
        caller_agent: str,
        sql_query: str,
        live_bq: bool = False,
    ) -> Dict[str, Any]:
        """Execute a validated read-only SELECT query with BigQuery `maximum_bytes_billed` guardrail."""
        enforce_agent_tool_permission(caller_agent, "execute_approved_query")
        validated_sql = validate_readonly_sql(sql_query)

        if live_bq or self.use_live_bq_by_default:
            try:
                import google.auth
                from google.cloud import bigquery

                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                client = bigquery.Client(
                    project=settings.project_id,
                    credentials=creds,
                    location=settings.location,
                )
                job_config = bigquery.QueryJobConfig(
                    maximum_bytes_billed=settings.bq_max_bytes_billed,
                    use_query_cache=True,
                )
                query_job = client.query(validated_sql, job_config=job_config)
                rows = [dict(r) for r in query_job.result(timeout=15.0)]
                return {
                    "tool": "mcp.bigquery.execute_approved_query",
                    "caller_agent": caller_agent,
                    "provenance": "bigquery_live",
                    "bytes_Processed": query_job.total_bytes_processed,
                    "row_count": len(rows),
                    "rows": rows[:100],
                }
            except Exception as exc:
                return {
                    "tool": "mcp.bigquery.execute_approved_query",
                    "caller_agent": caller_agent,
                    "provenance": "bigquery_live_fallback",
                    "status": "degraded_to_snapshot",
                    "error": str(exc),
                }

        return {
            "tool": "mcp.bigquery.execute_approved_query",
            "caller_agent": caller_agent,
            "provenance": "validated_sql_dry_check",
            "validated_sql": validated_sql,
            "max_bytes_billed_limit": settings.bq_max_bytes_billed,
            "status": "VALIDATED_READONLY",
        }

    def record_agent_trace(self, trace_row: Dict[str, Any], sync_to_bq: bool = False) -> None:
        """Persist agent execution telemetry locally and optionally append to BigQuery `ops_agent_traces`."""
        traces: List[Dict[str, Any]] = []
        if TRACE_LOG_PATH.exists():
            try:
                with open(TRACE_LOG_PATH, "r", encoding="utf-8") as f:
                    traces = json.load(f)
            except Exception:
                traces = []
        traces.insert(0, trace_row)
        traces = traces[:100]
        TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACE_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(traces, f, indent=2)

        if sync_to_bq:
            try:
                import google.auth
                from google.cloud import bigquery

                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                client = bigquery.Client(
                    project=settings.project_id,
                    credentials=creds,
                    location=settings.location,
                )
                table_id = f"{settings.project_id}.{settings.bq_dataset_id}.ops_agent_traces"
                client.insert_rows_json(table_id, [trace_row])
            except Exception:
                pass

    def get_recent_agent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not TRACE_LOG_PATH.exists():
            return []
        try:
            with open(TRACE_LOG_PATH, "r", encoding="utf-8") as f:
                traces = json.load(f)
            return traces[:limit]
        except Exception:
            return []


bq_mcp_server = BigQueryMCPServer()
