"""Integration Tests for all 11 Specialized Agents, Dynamic Orchestrator,
and Google ADK Root Agent (`tests.integration.test_orchestrator_and_agents`).
"""

import unittest
from orchestration.contracts import CompletionStatus, ResearchIntent
from services.agents.specialists import SPECIALIZED_AGENT_REGISTRY
from services.orchestrator.engine import orchestrator_engine
from services.root_agent.agent import build_adk_root_agent, root_agent_service


class TestOrchestratorAndAgents(unittest.TestCase):
    def test_all_eleven_specialized_agents_contract_compliance(self) -> None:
        self.assertEqual(len(SPECIALIZED_AGENT_REGISTRY), 11)
        context = {"ticker": "NVDA", "enable_live_vertex": False}
        for name, agent in SPECIALIZED_AGENT_REGISTRY.items():
            res = agent.execute(request_id=f"test-{name}", context=context)
            self.assertEqual(res.agent_name, name)
            self.assertIn(res.status, (CompletionStatus.COMPLETED, CompletionStatus.ABSTAINED))
            self.assertIsNotNone(res.uncertainty)
            self.assertGreaterEqual(len(res.citations), 1, msg=f"Agent {name} missing citations")
            self.assertEqual(len(res.errors), 0, msg=f"Agent {name} had errors: {res.errors}")

    def test_orchestrator_rejects_unapproved_dynamic_agent(self) -> None:
        with self.assertRaises(ValueError):
            orchestrator_engine.build_execution_plan(
                intent=ResearchIntent.STOCK_ANALYSIS,
                custom_agents=["market_data_agent", "arbitrary_code_execution_agent"],
            )

    def test_orchestrator_full_workflow_and_critic_gate(self) -> None:
        out = orchestrator_engine.execute_workflow(
            intent=ResearchIntent.STOCK_ANALYSIS,
            ticker="MSFT",
            user_query="Analyze MSFT technical, fundamental, and 5d forecast outlook",
            enable_live_vertex=False,
        )
        self.assertEqual(out["ticker"], "MSFT")
        self.assertEqual(out["governance_verdict"], "PASS")
        self.assertIn("APPROVED", out["critic_verdict"])
        self.assertTrue(out["publication_allowed"])
        self.assertIn("data_governance_agent", out["agents_executed"])
        self.assertIn("critic_agent", out["agents_executed"])
        self.assertIn("recommendation_agent", out["agents_executed"])

    def test_root_agent_and_google_adk_integration(self) -> None:
        adk_agent = build_adk_root_agent()
        self.assertEqual(adk_agent.name, "ami_root_agent")

        dossier = root_agent_service.handle_research_request(
            user_query="What are the catalysts, 5d forecast probabilities, and downside risks for AAPL?",
            ticker="AAPL",
            enable_live_vertex=False,
        )
        self.assertEqual(dossier["target_ticker"], "AAPL")
        self.assertIn("epistemic_breakdown", dossier)
        eb = dossier["epistemic_breakdown"]
        self.assertIn("measured_historical_facts", eb)
        self.assertIn("calibrated_model_forecasts", eb)
        self.assertIn("agent_interpretations_and_scenarios", eb)
        self.assertGreater(len(dossier["citations"]), 0)


if __name__ == "__main__":
    unittest.main()
