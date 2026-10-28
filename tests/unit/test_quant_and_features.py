"""Unit Tests for Point-in-Time Feature Engineering, Anti-Leakage Validation,
Calibration Metrics, and Walk-Forward Backtesting (`tests.unit.test_quant_and_features`).
"""

import unittest
import numpy as np
import pandas as pd
from data.features.engineer import FEATURE_COLUMNS, compute_point_in_time_features
from data.quality.validator import validate_market_dataset
from models.backtesting.engine import run_walk_forward_backtest
from models.evaluation.metrics import (
    compute_brier_metrics,
    compute_calibration_curve_and_ece,
    compute_precision_at_k,
    compute_roc_auc,
)


class TestQuantAndFeatures(unittest.TestCase):
    def setUp(self) -> None:
        dates = pd.bdate_range("2025-01-01", periods=100).date
        rows = []
        for ticker, base_p in [("NVDA", 120.0), ("SPY", 500.0)]:
            for i, d in enumerate(dates):
                close = base_p * (1.0 + 0.002 * i + 0.01 * np.sin(i / 4.0))
                rows.append(
                    {
                        "security_id": f"sec-{ticker.lower()}",
                        "ticker": ticker,
                        "trade_date": d,
                        "open_price": close * 0.995,
                        "high_price": close * 1.01,
                        "low_price": close * 0.99,
                        "close_price": close,
                        "adj_close": close,
                        "volume": 10_000_000 + i * 50_000,
                    }
                )
        self.ohlcv_df = pd.DataFrame(rows)
        self.spy_df = self.ohlcv_df[self.ohlcv_df["ticker"] == "SPY"].copy()

    def test_point_in_time_anti_leakage_fundamentals(self) -> None:
        """Verify that a future SEC filing is NOT visible prior to its filing_timestamp."""
        pit_fund = pd.DataFrame(
            [
                {
                    "ticker": "NVDA",
                    "period_end_date": "2024-12-31",
                    "filing_timestamp": "2025-02-01T16:00:00+00:00",
                    "rev_growth_yoy": 0.15,
                    "operating_margin": 0.25,
                    "eps_diluted": 3.0,
                    "total_debt": 5e9,
                    "cash_and_equiv": 10e9,
                },
                {
                    "ticker": "NVDA",
                    "period_end_date": "2025-03-31",
                    # Filed late in May 2025
                    "filing_timestamp": "2025-05-10T16:00:00+00:00",
                    "rev_growth_yoy": 0.85,
                    "operating_margin": 0.55,
                    "eps_diluted": 6.0,
                    "total_debt": 4e9,
                    "cash_and_equiv": 20e9,
                },
            ]
        )
        feats = compute_point_in_time_features(
            ohlcv_df=self.ohlcv_df, spy_df=self.spy_df, pit_fundamentals_df=pit_fund
        )
        nvda_feats = feats[feats["ticker"] == "NVDA"].copy()
        nvda_feats["trade_date_str"] = nvda_feats["trade_date"].astype(str)

        # In April 2025 (after period_end_date 2025-03-31, but BEFORE filing_timestamp 2025-05-10),
        # rev_growth_yoy_pit MUST still be 0.15, NOT 0.85!
        april_rows = nvda_feats[
            (nvda_feats["trade_date_str"] >= "2025-04-01")
            & (nvda_feats["trade_date_str"] <= "2025-05-05")
        ]
        self.assertGreater(len(april_rows), 0)
        for val in april_rows["rev_growth_yoy_pit"]:
            self.assertAlmostEqual(float(val), 0.15, places=4)

        # After 2025-05-12, the new filing is public and rev_growth_yoy_pit updates to 0.85
        late_may_rows = nvda_feats[nvda_feats["trade_date_str"] >= "2025-05-12"]
        self.assertGreater(len(late_may_rows), 0)
        for val in late_may_rows["rev_growth_yoy_pit"]:
            self.assertAlmostEqual(float(val), 0.85, places=4)

        # Verify all 18 feature columns exist and are finite
        for col in FEATURE_COLUMNS:
            self.assertIn(col, nvda_feats.columns)
            self.assertFalse(nvda_feats[col].isna().any())

    def test_probabilistic_calibration_metrics(self) -> None:
        y_true = np.array([0, 0, 1, 1, 1, 0, 1, 0, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.8, 0.75, 0.9, 0.3, 0.65, 0.25, 0.85, 0.7])
        auc = compute_roc_auc(y_true, y_prob)
        brier_res = compute_brier_metrics(y_true, y_prob)
        cal_res = compute_calibration_curve_and_ece(y_true, y_prob, n_bins=5)
        p_at_3 = compute_precision_at_k(y_true, y_prob, k=3)

        self.assertGreater(auc, 0.85)
        self.assertLess(brier_res["brier_score"], 0.12)
        self.assertGreater(brier_res["brier_skill_score"], 0.40)
        self.assertLess(cal_res["ece"], 0.25)
        self.assertEqual(p_at_3, 1.0)
        self.assertGreater(len(cal_res["bins"]), 0)

    def test_walk_forward_backtest_deducts_costs(self) -> None:
        dates = pd.bdate_range("2025-01-01", periods=30).date
        rows = []
        for d in dates:
            for idx, t in enumerate(["NVDA", "AAPL", "MSFT", "JPM", "LLY"]):
                rows.append(
                    {
                        "trade_date": d,
                        "ticker": t,
                        "pred_prob_up": 0.65 - idx * 0.03,
                        "fwd_raw_ret_pct": 1.2,
                        "spy_fwd_ret_pct": 0.8,
                        "y_up_actual": 1,
                    }
                )
        oos_df = pd.DataFrame(rows)
        res = run_walk_forward_backtest(
            oos_df=oos_df,
            horizon_days=5,
            model_version="v1.2.0-test",
            top_k=3,
            transaction_cost_bps=10.0,
            slippage_bps=5.0,
        )
        self.assertIn("sharpe_ratio", res)
        self.assertIn("equity_curve_json", res)
        # Verify net return reflects cost deduction
        self.assertEqual(res["transaction_cost_bps"], 10.0)
        self.assertEqual(res["slippage_bps"], 5.0)


if __name__ == "__main__":
    unittest.main()
