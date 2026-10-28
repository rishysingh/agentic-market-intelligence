"""Data Quality & Governance Specialized Agent Module."""
from services.agents.specialists import DataGovernanceAgent

agent = DataGovernanceAgent()
__all__ = ["DataGovernanceAgent", "agent"]
