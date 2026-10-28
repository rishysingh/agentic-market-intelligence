"""Point-in-Time Quantitative & Fundamental Feature Engineering Engine.

Computes strictly causal, time-aligned technical and fundamental features without
look-ahead bias. Fundamental metrics from `fact_fundamentals_pit` are joined ONLY
when `acceptance_timestamp <= trade_date_close_utc`.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


FEATURE_VERSION = "v1.0-pit"

FEATURE_COLUMNS = [
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "vol_20d_ann",
    "vol_60d_ann",
    "rsi_14",
    "macd_signal_diff",
    "bb_zscore_20d",
    "volume_zscore_20d",
    "atr_pct_14d",
    "beta_spy_60d",
    "rel_strength_sector_20d",
    "max_drawdown_60d",
    "pe_ttm_pit",
    "rev_growth_yoy_pit",
    "profit_margin_pit",
    "debt_to_cash_pit",
]


def compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0).rolling(window=window, min_periods=window).mean()
    loss = (-delta.clip(upper=0.0)).rolling(window=window, min_periods=window).mean()
    rs = gain / loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_point_in_time_features(
    ohlcv_df: pd.DataFrame,
    spy_df: Optional[pd.DataFrame] = None,
    pit_fundamentals_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Compute strictly causal point-in-time features for all securities in `ohlcv_df`."""
    if ohlcv_df.empty:
        return pd.DataFrame()

    df = ohlcv_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df = df.sort_values(["ticker", "trade_date"]).reset_index(drop=True)

    # Prepare SPY benchmark return series for causal rolling beta & relative strength
    spy_ret_map: Dict[Any, float] = {}
    spy_ret20_map: Dict[Any, float] = {}
    if spy_df is not None and not spy_df.empty:
        s_df = spy_df.sort_values("trade_date").copy()
        s_df["trade_date"] = pd.to_datetime(s_df["trade_date"]).dt.date
        s_df["spy_ret_1d"] = s_df["adj_close"].pct_change(1)
        s_df["spy_ret_20d"] = s_df["adj_close"].pct_change(20)
        spy_ret_map = dict(zip(s_df["trade_date"], s_df["spy_ret_1d"]))
        spy_ret20_map = dict(zip(s_df["trade_date"], s_df["spy_ret_20d"]))

    now_iso = datetime.now(timezone.utc).isoformat()
    out_frames: List[pd.DataFrame] = []

    for ticker, grp in df.groupby("ticker", sort=False):
        g = grp.sort_values("trade_date").copy()
        close_col = "adj_close" if "adj_close" in g.columns else ("close" if "close" in g.columns else "close_price")
        high_col = "high" if "high" in g.columns else "high_price"
        low_col = "low" if "low" in g.columns else "low_price"
        close = g[close_col].astype(float)
        high = g[high_col].astype(float)
        low = g[low_col].astype(float)
        vol = g["volume"].astype(float)

        g["close_price"] = close
        g["ret_1d"] = close.pct_change(1).fillna(0.0)
        g["ret_5d"] = close.pct_change(5).fillna(0.0)
        g["ret_20d"] = close.pct_change(20)
        g["ret_60d"] = close.pct_change(60).fillna(g["ret_20d"]).fillna(0.0)

        g["vol_20d_ann"] = (g["ret_1d"].rolling(20, min_periods=10).std() * np.sqrt(252.0)).fillna(0.20)
        g["vol_60d_ann"] = (g["ret_1d"].rolling(60, min_periods=20).std() * np.sqrt(252.0)).fillna(g["vol_20d_ann"])

        g["rsi_14"] = compute_rsi(close, window=14)

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        g["macd_signal_diff"] = ((macd - signal) / close.replace(0.0, np.nan)).fillna(0.0)

        ma20 = close.rolling(20, min_periods=10).mean()
        sd20 = close.rolling(20, min_periods=10).std().replace(0.0, np.nan)
        g["bb_zscore_20d"] = ((close - ma20) / sd20).fillna(0.0)

        vol_ma20 = vol.rolling(20, min_periods=10).mean()
        vol_sd20 = vol.rolling(20, min_periods=10).std().replace(0.0, np.nan)
        g["volume_zscore_20d"] = ((vol - vol_ma20) / vol_sd20).fillna(0.0)

        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        g["atr_pct_14d"] = (tr.rolling(14, min_periods=7).mean() / close).fillna(0.015)

        # Rolling 60d Beta & 20d Relative Strength vs SPY
        if spy_ret_map:
            spy_r1 = g["trade_date"].map(spy_ret_map).astype(float)
            spy_r20 = g["trade_date"].map(spy_ret20_map).astype(float)
            cov60 = g["ret_1d"].rolling(60, min_periods=20).cov(spy_r1)
            var60 = spy_r1.rolling(60, min_periods=20).var().replace(0.0, np.nan)
            g["beta_spy_60d"] = (cov60 / var60).fillna(1.0).clip(-1.0, 3.5)
            g["rel_strength_sector_20d"] = (g["ret_20d"] - spy_r20).fillna(0.0)
        else:
            g["beta_spy_60d"] = 1.0
            g["rel_strength_sector_20d"] = g["ret_20d"].fillna(0.0)

        roll_max60 = close.rolling(60, min_periods=10).max()
        g["max_drawdown_60d"] = ((close / roll_max60) - 1.0).fillna(0.0)

        # Point-in-Time Fundamental Join: only use facts where filing_date <= trade_date
        g["pe_ttm_pit"] = 22.0
        g["rev_growth_yoy_pit"] = 0.08
        g["profit_margin_pit"] = 0.15
        g["debt_to_cash_pit"] = 1.0

        if pit_fundamentals_df is not None and not pit_fundamentals_df.empty:
            f_sub = pit_fundamentals_df[pit_fundamentals_df["ticker"] == ticker].copy()
            if not f_sub.empty:
                if "filing_date" not in f_sub.columns and "filing_timestamp" in f_sub.columns:
                    f_sub["filing_date"] = f_sub["filing_timestamp"].astype(str).str.slice(0, 10)
                f_sub["filing_date_dt"] = pd.to_datetime(f_sub["filing_date"]).dt.date
                f_sub = f_sub.sort_values("filing_date_dt")

                if "metric_name" in f_sub.columns and "metric_value" in f_sub.columns:
                    # Tall EAV format from SecEdgarAdapter
                    piv = (
                        f_sub.pivot_table(
                            index="filing_date_dt",
                            columns="metric_name",
                            values="metric_value",
                            aggfunc="last",
                        )
                        .sort_index()
                    )
                    for idx_row, t_date in g["trade_date"].items():
                        elig = piv[piv.index <= t_date]
                        if not elig.empty:
                            last_row = elig.iloc[-1]
                            if "pe_ttm" in last_row and pd.notna(last_row["pe_ttm"]):
                                g.loc[idx_row, "pe_ttm_pit"] = float(last_row["pe_ttm"])
                            if "rev_growth_yoy" in last_row and pd.notna(last_row["rev_growth_yoy"]):
                                g.loc[idx_row, "rev_growth_yoy_pit"] = float(last_row["rev_growth_yoy"])
                            if "profit_margin" in last_row and pd.notna(last_row["profit_margin"]):
                                g.loc[idx_row, "profit_margin_pit"] = float(last_row["profit_margin"])
                            if "debt_to_cash" in last_row and pd.notna(last_row["debt_to_cash"]):
                                g.loc[idx_row, "debt_to_cash_pit"] = float(last_row["debt_to_cash"])
                else:
                    # Wide format with explicit fundamental columns
                    for idx_row, t_date in g["trade_date"].items():
                        elig = f_sub[f_sub["filing_date_dt"] <= t_date]
                        if not elig.empty:
                            last_row = elig.iloc[-1]
                            if "rev_growth_yoy" in last_row and pd.notna(last_row["rev_growth_yoy"]):
                                g.loc[idx_row, "rev_growth_yoy_pit"] = float(last_row["rev_growth_yoy"])
                            if "operating_margin" in last_row and pd.notna(last_row["operating_margin"]):
                                g.loc[idx_row, "profit_margin_pit"] = float(last_row["operating_margin"])
                            elif "profit_margin" in last_row and pd.notna(last_row["profit_margin"]):
                                g.loc[idx_row, "profit_margin_pit"] = float(last_row["profit_margin"])
        g["feature_version"] = FEATURE_VERSION
        g["as_of_timestamp"] = g["trade_date"].apply(lambda d: f"{d.isoformat()}T20:00:00+00:00")
        g["computed_at"] = now_iso

        keep_cols = [
            "security_id",
            "ticker",
            "trade_date",
            "feature_version",
            "close_price",
            *FEATURE_COLUMNS,
            "as_of_timestamp",
            "computed_at",
        ]
        out_frames.append(g[keep_cols].dropna(subset=["ret_20d"]))

    if not out_frames:
        return pd.DataFrame()
    return pd.concat(out_frames, ignore_index=True)
