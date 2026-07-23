"""
Evaluation metrics for H-TRACE — covering *all* evaluation dimensions:

  Detection (faults)   : precision, recall, F1, ROC-AUC, PR-AUC
  Forecast  (traffic)  : MAE, RMSE, MAPE, sMAPE, R^2
  Safety    (gate)     : false-pass rate, false-block rate, hallucination rate
  Operations (latency) : mean / p95 decision latency, meets-Near-RT-RIC

Plus the Rule-of-Three statistical bound used to certify the zero-defect claims.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
from sklearn.metrics import (average_precision_score, f1_score,
                             precision_score, recall_score, roc_auc_score)

# Near-Real-Time RIC execution window upper bound (ms). Decisions must fit here.
NEAR_RT_RIC_MS = 100.0


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def detection_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                      y_score: np.ndarray | None = None) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    out = {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    if y_score is not None and len(np.unique(y_true)) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, y_score))
        out["pr_auc"] = float(average_precision_score(y_true, y_score))
    else:
        out["roc_auc"] = float("nan")
        out["pr_auc"] = float("nan")
    return out


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #
def forecast_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    denom = np.clip(np.abs(y_true), 1.0, None)          # avoid /0 on the 0-scale
    mape = float(np.mean(np.abs(err) / denom) * 100.0)
    smape = float(np.mean(2 * np.abs(err) /
                          (np.abs(y_true) + np.abs(y_pred) + 1e-9)) * 100.0)
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2)) + 1e-9
    r2 = 1.0 - ss_res / ss_tot
    return {"mae": mae, "rmse": rmse, "mape": mape, "smape": smape, "r2": r2}


# --------------------------------------------------------------------------- #
# Safety
# --------------------------------------------------------------------------- #
def safety_metrics(n_unsafe_presented: int, n_unsafe_passed: int,
                   n_safe_presented: int, n_safe_blocked: int,
                   n_actions_total: int, n_malformed_executed: int
                   ) -> Dict[str, float]:
    """
    false_pass_rate    : unsafe actions that were (wrongly) executed   -> want 0
    false_block_rate   : safe actions that were (wrongly) blocked      -> want low
    hallucination_rate : malformed actions that reached the equipment  -> want 0
    """
    fpr = (n_unsafe_passed / n_unsafe_presented) if n_unsafe_presented else 0.0
    fbr = (n_safe_blocked / n_safe_presented) if n_safe_presented else 0.0
    halluc = (n_malformed_executed / n_actions_total) if n_actions_total else 0.0
    return {
        "false_pass_rate": 100.0 * fpr,
        "false_block_rate": 100.0 * fbr,
        "hallucination_rate": 100.0 * halluc,
        "n_unsafe_presented": n_unsafe_presented,
        "n_unsafe_passed": n_unsafe_passed,
    }


# --------------------------------------------------------------------------- #
# Latency
# --------------------------------------------------------------------------- #
def latency_metrics(latencies_ms) -> Dict[str, float]:
    arr = np.asarray(latencies_ms, dtype=float)
    if arr.size == 0:
        return {"latency_mean_ms": float("nan"), "latency_p95_ms": float("nan"),
                "meets_near_rt": 0.0}
    return {
        "latency_mean_ms": float(np.mean(arr)),
        "latency_p95_ms": float(np.percentile(arr, 95)),
        "meets_near_rt": float(np.mean(arr <= NEAR_RT_RIC_MS) * 100.0),
    }


# --------------------------------------------------------------------------- #
# Statistical certification
# --------------------------------------------------------------------------- #
def rule_of_three(n_trials: int, n_failures: int) -> Dict[str, float]:
    """
    For 0 observed failures, the true rate is < 3/n at 95% confidence.
    Returns the observed rate and the 95% upper confidence bound.
    """
    rate = (n_failures / n_trials) if n_trials else float("nan")
    upper95 = (3.0 / n_trials) if (n_trials and n_failures == 0) else float("nan")
    return {"observed_rate": rate, "upper95_bound": upper95, "n_trials": n_trials}


if __name__ == "__main__":
    print("detection:", detection_metrics(
        [0, 0, 1, 1], [0, 1, 1, 1], [0.1, 0.4, 0.8, 0.9]))
    print("forecast :", forecast_metrics([100, 200, 300], [110, 190, 305]))
    print("safety   :", safety_metrics(50, 0, 20, 1, 500, 0))
    print("latency  :", latency_metrics([2.1, 3.4, 5.0, 8.2]))
    print("rule3    :", rule_of_three(500, 0))
