"""
Volatility-gated forecaster experiment (supervisor's Week-7 design suggestion).

Motivation
----------
On the aggregate metric the LSTM wins MAE/RMSE but loses R^2 to a trivial
persistence baseline. The reason (confirmed in the per-KPI breakdown) is that
near-constant series such as `sessions` are forecast almost perfectly by
persistence, while the LSTM's real value shows up on volatile traffic
(internet / downstream). The supervisor's advice was to "gate LSTM usage on KPI
volatility": use the LSTM only where the signal is volatile enough to benefit,
and fall back to persistence on near-constant series.

This script implements exactly that as a deployable rule and measures it:

    volatility(series)  = coefficient of variation of the TRAIN split
                        = std(train) / mean(train)          (observable at deploy time)
    gate:  CV >= TAU  -> LSTM (H-TRACE)      # volatile   -> learned model helps
           CV <  TAU  -> Persistence         # near-flat  -> trivial model is better

The gate uses only the training split, so there is no test leakage. We then
report LSTM vs Persistence vs Volatility-Gated over the held-out tail of every
series, aggregated by the median (same aggregation as the main notebook).

Run:
    python -m experiments.volatility_gated_forecast          # sample (fast)
    HTRACE_FULL=1 python -m experiments.volatility_gated_forecast   # all 62 series
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from src import config as C
from src.baselines.forecasters import PersistenceForecaster
from src.data_loader import load_all
from src.evaluation import metrics as M
from src.models.traffic_predictor import LSTMPredictor
from src.preprocessing import build_feature_frame, chronological_split

# Volatility threshold: series with a train coefficient-of-variation below this
# are treated as "near-constant" and forecast with persistence. 0.15 cleanly
# separates the flat `sessions` streams from the volatile internet/downstream.
TAU = float(os.environ.get("HTRACE_VOL_TAU", "0.15"))


def _train_cv(train: np.ndarray) -> float:
    train = np.asarray(train, dtype=float)
    mu = float(np.mean(train))
    if abs(mu) < 1e-9:
        return float("inf")
    return float(np.std(train) / mu)


def run(sample: bool) -> pd.DataFrame:
    series_list = load_all(sample=sample)
    w, h = C.LSTM_PARAMS["input_window"], C.LSTM_PARAMS["horizon"]
    per_series = []

    for i, s in enumerate(series_list, 1):
        vals = build_feature_frame(s)["value"].to_numpy()
        train, test = chronological_split(vals, C.LSTM_PARAMS["train_frac"])
        cv = _train_cv(train)

        lstm = LSTMPredictor().fit(train)
        seed = np.concatenate([train[-w:], test])
        y_true = seed[w + h - 1:]
        preds = {
            "LSTM (H-TRACE)": lstm.predict_series(seed),
            "Persistence": PersistenceForecaster().predict_series(seed),
        }
        # Volatility gate — pick the deployable forecaster for this series.
        use_lstm = cv >= TAU
        preds["Volatility-Gated"] = preds["LSTM (H-TRACE)"] if use_lstm else preds["Persistence"]

        row = {"series_id": s.series_id, "kpi_type": s.kpi_type, "kind": s.kind,
               "train_cv": round(cv, 4), "gate_choice": "LSTM" if use_lstm else "Persistence"}
        for name, yp in preds.items():
            m = min(len(y_true), len(yp))
            fm = M.forecast_metrics(y_true[:m], yp[:m])
            for k, v in fm.items():
                row[f"{name}|{k}"] = v
        per_series.append(row)
        print(f"  [{i:>2}/{len(series_list)}] {s.series_id:>4} {s.kpi_type:<10} "
              f"CV={cv:5.2f} -> {'LSTM' if use_lstm else 'Persistence'}")

    return pd.DataFrame(per_series)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    methods = ["LSTM (H-TRACE)", "Persistence", "Volatility-Gated"]
    metrics = ["mae", "rmse", "mape", "smape", "r2"]
    rows = []
    for name in methods:
        row = {"forecaster": name}
        for k in metrics:
            row[k] = float(df[f"{name}|{k}"].median())
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    sample = os.environ.get("HTRACE_FULL", "0") != "1"
    print(f"Volatility-gated forecast experiment | mode={'SAMPLE' if sample else 'FULL'} "
          f"| TAU={TAU}")
    per_series = run(sample)
    summary = summarise(per_series)

    # How the gate split the series, and whether it tracks volatility.
    chose_lstm = per_series[per_series["gate_choice"] == "LSTM"]
    chose_pers = per_series[per_series["gate_choice"] == "Persistence"]

    print("\n=== Aggregate (median over series) ===")
    print(summary.round(3).to_string(index=False))
    print(f"\nGate: {len(chose_lstm)} series -> LSTM (mean CV "
          f"{chose_lstm['train_cv'].mean():.2f}), "
          f"{len(chose_pers)} series -> Persistence (mean CV "
          f"{chose_pers['train_cv'].mean():.2f})")
    if not chose_pers.empty:
        print("Persistence-gated KPI types: "
              + ", ".join(sorted(chose_pers["kpi_type"].unique())))

    per_series.to_csv(C.TABLES_DIR / "forecast_volatility_gated_per_series.csv", index=False)
    summary.round(4).to_csv(C.TABLES_DIR / "forecast_volatility_gated.csv", index=False)
    print(f"\nWrote: {C.TABLES_DIR / 'forecast_volatility_gated.csv'}")
    print(f"Wrote: {C.TABLES_DIR / 'forecast_volatility_gated_per_series.csv'}")
