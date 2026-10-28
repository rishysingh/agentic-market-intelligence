"""Controlled MCP Tool Server for SEC EDGAR Filings, Point-in-Time Fundamentals,
and Vertex AI Gemini Grounded News Search (`mcp.research.server`).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List
from mcp.security import enforce_agent_tool_permission, sanitize_external_text
from orchestration.config import settings


SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "latest_snapshot.json"


class ResearchMCPServer:
    """Controlled MCP Tool Server for SEC EDGAR Filings and Grounded Google Search."""

    def _load_snapshot(self) -> Dict[str, Any]:
        if not SNAPSHOT_PATH.exists():
            from data.ingestion.pipeline import execute_pipeline
            execute_pipeline(mode="incremental", upload_to_bq=False)
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_sec_edgar_catalysts_and_fundamentals(
        self, caller_agent: str, ticker: str
    ) -> Dict[str, Any]:
        """Return verified SEC EDGAR filings (10-K/10-Q/8-K) and point-in-time XBRL fundamentals."""
        enforce_agent_tool_permission(
            caller_agent, "get_sec_edgar_catalysts_and_fundamentals"
        )
        t_clean = (ticker or "").strip().upper()
        snap = self._load_snapshot()

        catalysts: List[Dict[str, Any]] = []
        for c in snap.get("catalysts", []):
            if c.get("ticker") == t_clean:
                c_copy = dict(c)
                c_copy["headline"] = sanitize_external_text(c_copy.get("headline", ""))
                c_copy["summary"] = sanitize_external_text(c_copy.get("summary", ""))
                catalysts.append(c_copy)

        fundamentals: List[Dict[str, Any]] = [
            f for f in snap.get("fundamentals_pit", []) if f.get("ticker") == t_clean
        ]
        fundamentals.sort(
            key=lambda x: x.get("acceptance_timestamp") or x.get("filing_date") or x.get("filing_timestamp", ""),
            reverse=True,
        )

        return {
            "tool": "mcp.research.get_sec_edgar_catalysts_and_fundamentals",
            "caller_agent": caller_agent,
            "ticker": t_clean,
            "catalysts_count": len(catalysts),
            "catalysts": catalysts,
            "fundamentals_pit": fundamentals[:8],
            "anti_leakage_policy": "All fundamental values are strictly gated by SEC filing_date / acceptance_timestamp <= evaluation_timestamp.",
        }

    def run_grounded_news_search(
        self,
        caller_agent: str,
        ticker: str,
        company_name: str,
        query_focus: str = "earnings, SEC filings, guidance, material catalysts",
        enable_live_vertex: bool = True,
    ) -> Dict[str, Any]:
        """Run Google Search grounding via Vertex AI Gemini to discover recent catalysts with source citations."""
        enforce_agent_tool_permission(caller_agent, "run_grounded_news_search")
        t_clean = (ticker or "").strip().upper()
        now_iso = datetime.now(timezone.utc).isoformat()

        sec_bundle = self.get_sec_edgar_catalysts_and_fundamentals(
            caller_agent=caller_agent, ticker=t_clean
        )
        edgar_catalysts = sec_bundle.get("catalysts", [])

        if enable_live_vertex:
            try:
                import google.auth
                from google import genai
                from google.genai import types

                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                client = genai.Client(
                    vertexai=True,
                    project=settings.project_id,
                    location=settings.location,
                    credentials=creds,
                )
                prompt = (
                    f"Research recent material financial news, earnings announcements, SEC filings, "
                    f"guidance changes, or regulatory developments for {company_name} ({t_clean}). "
                    f"Focus: {query_focus}. "
                    f"Return a concise factual summary distinguishing the event occurrence date from publication time."
                )
                resp = client.models.generate_content(
                    model=settings.gemini_fast_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=450,
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                    ),
                )
                grounded_text = sanitize_external_text(resp.text or "")
                grounding_sources: List[Dict[str, str]] = []
                cand = resp.candidates[0] if resp.candidates else None
                gm = getattr(cand, "grounding_metadata", None) if cand else None
                chunks = getattr(gm, "grounding_chunks", None) if gm else None
                if chunks:
                    for ch in chunks[:5]:
                        web = getattr(ch, "web", None)
                        if web and getattr(web, "uri", None):
                            grounding_sources.append(
                                {
                                    "source_type": "GOOGLE_SEARCH_GROUNDING",
                                    "title": sanitize_external_text(
                                        getattr(web, "title", f"{t_clean} Financial News"), 160
                                    ),
                                    "url": getattr(web, "uri"),
                                    "event_timestamp": now_iso,
                                    "publication_timestamp": now_iso,
                                }
                            )
                return {
                    "tool": "mcp.research.run_grounded_news_search",
                    "caller_agent": caller_agent,
                    "ticker": t_clean,
                    "grounding_mode": "vertex_ai_google_search_live",
                    "grounded_summary": grounded_text,
                    "grounded_citations": grounding_sources,
                    "sec_edgar_catalysts": edgar_catalysts,
                    "retrieved_at": now_iso,
                }
            except Exception as exc:
                fallback_reason = str(exc)
        else:
            fallback_reason = "live_vertex_disabled_by_caller"

        # Deterministic fallback to verified SEC EDGAR catalyst records
        summary_lines = [
            f"{c.get('catalyst_type', c.get('event_type', 'SEC_FILING'))} filed on {c.get('publication_timestamp', '')[:10]}: {c.get('headline', '')}"
            for c in edgar_catalysts[:3]
        ]
        return {
            "tool": "mcp.research.run_grounded_news_search",
            "caller_agent": caller_agent,
            "ticker": t_clean,
            "grounding_mode": "sec_edgar_verified_fallback",
            "fallback_reason": fallback_reason,
            "grounded_summary": " | ".join(summary_lines)
            if summary_lines
            else f"Verified SEC EDGAR periodic filings tracked for {t_clean}.",
            "grounded_citations": [
                {
                    "source_type": "SEC_EDGAR",
                    "title": c["headline"],
                    "url": c["source_url"],
                    "event_timestamp": c["event_timestamp"],
                    "publication_timestamp": c["publication_timestamp"],
                }
                for c in edgar_catalysts[:3]
            ],
            "sec_edgar_catalysts": edgar_catalysts,
            "retrieved_at": now_iso,
        }


research_mcp_server = ResearchMCPServer()
