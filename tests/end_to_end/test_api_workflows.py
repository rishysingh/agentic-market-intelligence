"""End-to-End API Tests for Tier 2 FastAPI Service (`tests.end_to_end.test_api_workflows`)."""

import unittest
from fastapi.testclient import TestClient
from orchestration.config import settings
from services.api.main import app


class TestEndToEndAPIWorkflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertEqual(len(data["agent_registry"]), 11)
        self.assertEqual(data["data_quality"]["verdict"], "PASS")

    def test_market_overview_endpoint(self) -> None:
        resp = self.client.get("/api/v1/market/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("market_regime", data)
        self.assertIn("regime_classification", data["market_regime"])
        self.assertGreater(len(data["top_opportunities"]), 0)
        self.assertIn("volume_anomalies", data["signal_monitors"])

    def test_opportunities_filtering_and_ranking(self) -> None:
        resp = self.client.get("/api/v1/opportunities?limit=10&sector=Information%20Technology")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["count"], 0)
        for item in data["opportunities"]:
            self.assertEqual(item["sector"], "Information Technology")
            self.assertIn("score_breakdown", item)
            self.assertIn("unsuitability_flags", item)

    def test_stock_dossier_valid_and_invalid_ticker(self) -> None:
        resp = self.client.get("/api/v1/stocks/NVDA")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ticker"], "NVDA")
        self.assertEqual(len(data["forecasts_by_horizon"]), 3)
        self.assertGreater(len(data["price_history"]["bars"]), 30)
        self.assertIn("bullish_scenario", data["recommendation_and_scenarios"])

        # Out-of-universe ticker should return 404
        resp_404 = self.client.get("/api/v1/stocks/INVALID")
        self.assertEqual(resp_404.status_code, 404)

    def test_performance_backtests_endpoint(self) -> None:
        resp = self.client.get("/api/v1/performance/backtests")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["backtest_runs"]), 3)
        self.assertEqual(len(data["model_registry"]), 3)

    def test_agent_research_post_endpoint(self) -> None:
        resp = self.client.post(
            "/api/v1/agent/research",
            json={
                "user_query": "Evaluate JPM risk profile, drawdown sensitivity, and 5d forecast.",
                "ticker": "JPM",
                "enable_live_vertex": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["target_ticker"], "JPM")
        self.assertTrue(data["publication_allowed"])
        self.assertIn("executive_summary", data)

    def test_protected_refresh_endpoint_requires_token(self) -> None:
        unauth = self.client.post("/api/v1/pipeline/refresh")
        self.assertEqual(unauth.status_code, 401)

        auth = self.client.post(
            "/api/v1/pipeline/refresh?mode=incremental",
            headers={"X-API-Key": settings.api_auth_token},
        )
        self.assertEqual(auth.status_code, 200)
        self.assertEqual(auth.json()["status"], "REFRESH_COMPLETED")


if __name__ == "__main__":
    unittest.main()
