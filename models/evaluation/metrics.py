"""Out-of-Sample Statistical Evaluation & Probability Calibration Metrics.

Provides deterministic, dependency-light implementations of:
- ROC-AUC (exact Mann-Whitney U rank statistic)
- Brier Score & Brier Skill Score (vs. climatological base rate)
- Expected Calibration Error (ECE) & Reliability Curve bins
- Precision@K for ranked stock opportunities
"""

from typing import Any, Dict, List
import numpy as np


def compute_roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Compute exact ROC-AUC via Mann-Whitney U rank statistic."""
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    n_pos = int(np.sum(y_true == 1))
    n_neg = int(np.sum(y_true == 0))
    if n_pos == 0 or n_neg == 0:
        return 0.5

    order = np.argsort(y_prob)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_prob) + 1, dtype=float)

    # Handle ties by averaging ranks
    unique_vals, inv, counts = np.unique(y_prob, return_inverse=True, return_counts=True)
    if np.any(counts > 1):
        for val_idx, cnt in enumerate(counts):
            if cnt > 1:
                mask = inv == val_idx
                ranks[mask] = float(np.mean(ranks[mask]))

    sum_pos_ranks = float(np.sum(ranks[y_true == 1]))
    u_stat = sum_pos_ranks - (n_pos * (n_pos + 1) / 2.0)
    auc = u_stat / float(n_pos * n_neg)
    return float(np.clip(auc, 0.0, 1.0))


def compute_brier_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, float]:
    """Compute Brier Score, Climatology Reference Brier Score, and Brier Skill Score."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1.0 - 1e-6)
    if len(y_true) == 0:
        return {"brier_score": 0.25, "brier_ref": 0.25, "brier_skill_score": 0.0}

    bs = float(np.mean((y_prob - y_true) ** 2))
    base_rate = float(np.mean(y_true))
    bs_ref = float(np.mean((base_rate - y_true) ** 2))
    if bs_ref <= 1e-9:
        bss = 0.0
    else:
        bss = float(1.0 - (bs / bs_ref))
    return {
        "brier_score": round(bs, 5),
        "brier_ref": round(bs_ref, 5),
        "brier_skill_score": round(bss, 5),
        "base_rate": round(base_rate, 5),
    }


def compute_calibration_curve_and_ece(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 8
) -> Dict[str, Any]:
    """Compute reliability curve buckets and Expected Calibration Error (ECE)."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) == 0:
        return {"ece": 0.0, "bins": []}

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins_out: List[Dict[str, Any]] = []
    ece = 0.0
    n_total = float(len(y_true))

    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        cnt = int(np.sum(mask))
        if cnt > 0:
            mean_pred = float(np.mean(y_prob[mask]))
            emp_freq = float(np.mean(y_true[mask]))
            gap = abs(mean_pred - emp_freq)
            ece += (cnt / n_total) * gap
            bins_out.append(
                {
                    "bin_index": i + 1,
                    "bin_range": f"{lo:.2f}-{hi:.2f}",
                    "count": cnt,
                    "mean_predicted_prob": round(mean_pred, 4),
                    "empirical_hit_rate": round(emp_freq, 4),
                    "calibration_gap": round(gap, 4),
                }
            )
    return {"ece": round(float(ece), 5), "bins": bins_out}


def compute_precision_at_k(y_true: np.ndarray, y_prob: np.ndarray, k: int = 10) -> float:
    """Compute top-K hit rate precision."""
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) == 0:
        return 0.0
    k_eff = min(k, len(y_true))
    top_idx = np.argsort(y_prob)[::-1][:k_eff]
    return round(float(np.mean(y_true[top_idx])), 4)
