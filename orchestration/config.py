"""Centralized configuration management for Agentic Market Intelligence Platform."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class PlatformConfig:
    """Immutable platform configuration loaded from environment variables."""

    project_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-03-c81d344a3430")
    )
    location: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    bq_dataset_id: str = field(
        default_factory=lambda: os.getenv("BQ_DATASET_ID", "market_intelligence")
    )
    bq_max_bytes_billed: int = field(
        default_factory=lambda: int(os.getenv("BQ_MAX_BYTES_BILLED", str(100 * 1024 * 1024)))
    )

    # Google ADK & Vertex AI Gemini models
    adk_root_model: str = field(
        default_factory=lambda: os.getenv("ADK_ROOT_MODEL", "gemini-2.5-pro")
    )
    adk_specialist_model: str = field(
        default_factory=lambda: os.getenv("ADK_SPECIALIST_MODEL", "gemini-2.5-flash")
    )
    adk_critic_model: str = field(
        default_factory=lambda: os.getenv("ADK_CRITIC_MODEL", "gemini-2.5-pro")
    )
    enable_search_grounding: bool = field(
        default_factory=lambda: os.getenv("ADK_ENABLE_SEARCH_GROUNDING", "true").lower() == "true"
    )

    # Orchestrator & execution guardrails
    max_parallel_agents: int = field(
        default_factory=lambda: int(os.getenv("ORCHESTRATOR_MAX_PARALLEL_AGENTS", "6"))
    )
    agent_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("ORCHESTRATOR_AGENT_TIMEOUT_SECONDS", "45.0"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("ORCHESTRATOR_MAX_RETRIES", "2"))
    )
    token_budget_per_request: int = field(
        default_factory=lambda: int(os.getenv("ORCHESTRATOR_TOKEN_BUDGET_PER_REQUEST", "32000"))
    )

    # Data quality & statistical forecast guardrails
    min_data_freshness_hours: float = field(
        default_factory=lambda: float(os.getenv("MIN_DATA_FRESHNESS_HOURS", "96.0"))
    )
    min_model_brier_skill_score: float = field(
        default_factory=lambda: float(os.getenv("MIN_MODEL_BRIER_SKILL_SCORE", "0.005"))
    )
    min_model_roc_auc: float = field(
        default_factory=lambda: float(os.getenv("MIN_MODEL_ROC_AUC", "0.52"))
    )
    min_history_trading_days: int = 60

    # Market data & SEC EDGAR
    sec_edgar_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "SEC_EDGAR_USER_AGENT",
            "AgenticMarketIntelligence/1.0 (institutional-research@qwiklabs.net)",
        )
    )
    market_data_provider: str = field(
        default_factory=lambda: os.getenv("MARKET_DATA_PRIMARY_PROVIDER", "stooq_eod")
    )
    polygon_api_key: str = field(default_factory=lambda: os.getenv("POLYGON_API_KEY", ""))
    alphavantage_api_key: str = field(default_factory=lambda: os.getenv("ALPHAVANTAGE_API_KEY", ""))
    tiingo_api_key: str = field(default_factory=lambda: os.getenv("TIINGO_API_KEY", ""))

    # Security & API settings
    api_auth_token: str = field(
        default_factory=lambda: os.getenv(
            "AMI_API_AUTH_TOKEN", "dev-local-research-token-change-in-prod"
        )
    )
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("AMI_RATE_LIMIT_PER_MINUTE", "60"))
    )

    @property
    def full_dataset_id(self) -> str:
        return f"{self.project_id}.{self.bq_dataset_id}"

    @property
    def gemini_pro_model(self) -> str:
        return self.adk_root_model

    @property
    def gemini_fast_model(self) -> str:
        return self.adk_specialist_model


settings = PlatformConfig()
