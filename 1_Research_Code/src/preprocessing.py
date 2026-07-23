"""
Preprocessing for H-TRACE.

Turns each raw KpiSeries into:
  * a regular 5-minute grid (gaps detected & interpolated),
  * engineered features for the Isolation-Forest anomaly detector
    (value, first difference, rolling mean/std, residual-from-rolling),
  * cyclical time-of-day / day-of-week features (the shifted timestamps still
    preserve relative daily seasonality, which drives Night/Festival regimes),
  * supervised windows (X, y) for the LSTM traffic predictor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd

from . import config as C
from .data_loader import KpiSeries


# --------------------------------------------------------------------------- #
# Regular grid + gap handling
# --------------------------------------------------------------------------- #
def regularise(series: KpiSeries) -> pd.DataFrame:
    """
    Reindex a series onto a complete 5-minute grid and interpolate short gaps.

    Returns a DataFrame indexed by sample number with columns:
        timestamp_s, value, is_anomaly, was_missing
    """
    step = C.SAMPLE_PERIOD_SEC
    t0, t1 = int(series.timestamps[0]), int(series.timestamps[-1])
    full_t = np.arange(t0, t1 + step, step)

    s = pd.Series(series.values, index=series.timestamps.astype(np.int64))
    s = s[~s.index.duplicated(keep="first")]
    s = s.reindex(full_t)

    was_missing = s.isna().to_numpy().astype(int)
    s = s.interpolate(method="linear", limit=C.INTERP_LIMIT, limit_direction="both")
    s = s.ffill().bfill()           # close any residual edge gaps

    # Re-map original incident sample indices onto the regular grid.
    orig_index = {int(t): i for i, t in enumerate(full_t)}
    labels = np.zeros(len(full_t), dtype=int)
    for start, end in series.incidents:
        # Original incidents are sample indices into the *raw* series; convert
        # via timestamp so they survive reindexing.
        if start < len(series.timestamps):
            ts_start = int(series.timestamps[start])
        else:
            continue
        end_idx = (len(series.timestamps) - 1) if end < 0 else min(end, len(series.timestamps) - 1)
        ts_end = int(series.timestamps[end_idx])
        gi = orig_index.get(ts_start, None)
        gj = orig_index.get(ts_end, None)
        if gi is not None and gj is not None:
            labels[gi:gj + 1] = 1

    return pd.DataFrame({
        "timestamp_s": full_t,
        "value": s.to_numpy(),
        "is_anomaly": labels,
        "was_missing": was_missing,
    })


# --------------------------------------------------------------------------- #
# Time features
# --------------------------------------------------------------------------- #
def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Cyclical time-of-day and day-of-week features from shifted timestamps."""
    sample_of_day = (df["timestamp_s"] // C.SAMPLE_PERIOD_SEC) % C.SAMPLES_PER_DAY
    day_index = (df["timestamp_s"] // C.SAMPLE_PERIOD_SEC) // C.SAMPLES_PER_DAY
    dow = day_index % 7

    df = df.copy()
    df["sample_of_day"] = sample_of_day
    df["tod_sin"] = np.sin(2 * np.pi * sample_of_day / C.SAMPLES_PER_DAY)
    df["tod_cos"] = np.cos(2 * np.pi * sample_of_day / C.SAMPLES_PER_DAY)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    return df


# --------------------------------------------------------------------------- #
# Anomaly-detector features
# --------------------------------------------------------------------------- #
ANOMALY_FEATURES = ["value", "diff1", "roll_mean", "roll_std", "residual"]


def add_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling-statistics features used by the Isolation Forest detector."""
    df = df.copy()
    w = C.ROLLING_WINDOW
    v = df["value"]
    df["diff1"] = v.diff().fillna(0.0)
    df["roll_mean"] = v.rolling(w, min_periods=1).mean()
    df["roll_std"] = v.rolling(w, min_periods=1).std().fillna(0.0)
    df["residual"] = v - df["roll_mean"]
    return df


def build_feature_frame(series: KpiSeries) -> pd.DataFrame:
    """Full preprocessing pipeline for one series."""
    df = regularise(series)
    df = add_time_features(df)
    df = add_anomaly_features(df)
    df["series_id"] = series.series_id
    df["kpi_type"] = series.kpi_type
    df["kind"] = series.kind
    df["area"] = series.area
    return df


# --------------------------------------------------------------------------- #
# LSTM windowing
# --------------------------------------------------------------------------- #
@dataclass
class Scaler:
    """Min-max scaler fitted on the training portion of one series."""
    lo: float
    hi: float

    def transform(self, x: np.ndarray) -> np.ndarray:
        rng = self.hi - self.lo
        return (x - self.lo) / rng if rng > 1e-9 else np.zeros_like(x)

    def inverse(self, x: np.ndarray) -> np.ndarray:
        return x * (self.hi - self.lo) + self.lo


def make_windows(values: np.ndarray, input_window: int, horizon: int
                 ) -> Tuple[np.ndarray, np.ndarray]:
    """Sliding windows: X[t] = values[t-w:t], y[t] = values[t+horizon-1]."""
    X, y = [], []
    n = len(values)
    for i in range(input_window, n - horizon + 1):
        X.append(values[i - input_window:i])
        y.append(values[i + horizon - 1])
    if not X:
        return np.empty((0, input_window)), np.empty((0,))
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)


def chronological_split(values: np.ndarray, train_frac: float
                        ) -> Tuple[np.ndarray, np.ndarray]:
    cut = int(len(values) * train_frac)
    return values[:cut], values[cut:]


if __name__ == "__main__":
    from .data_loader import load_all
    s = load_all(sample=True)[0]
    fdf = build_feature_frame(s)
    print(f"Series {s.series_id}: raw n={s.n} -> grid n={len(fdf)}")
    print("Columns:", list(fdf.columns))
    print(fdf[["timestamp_s", "value", "diff1", "roll_mean", "roll_std",
               "residual", "is_anomaly", "was_missing"]].describe().round(2))
