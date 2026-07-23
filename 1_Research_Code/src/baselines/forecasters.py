"""
Baseline traffic forecasters (for comparison against H-TRACE's LSTM).

The Tsourdinis-style anomaly-detection baseline has *no* predictive layer, so
H-TRACE's LSTM is compared against classic, model-free forecasters:

  * PersistenceForecaster   — predict the next value = the last value.
  * SeasonalNaiveForecaster — predict the value one day (288 samples) ago.

Both expose `predict_next(recent_values)` / `predict_series(values)` matching
the LSTM API so the forecast metrics are computed identically.
"""
from __future__ import annotations

import numpy as np

from .. import config as C


class PersistenceForecaster:
    """yhat[t] = value[t-1]."""

    horizon = C.LSTM_PARAMS["horizon"]
    input_window = C.LSTM_PARAMS["input_window"]
    _fitted = True

    def fit(self, *_a, **_k):
        return self

    def predict_next(self, recent_values: np.ndarray) -> float:
        return float(recent_values[-1])

    def predict_series(self, values: np.ndarray) -> np.ndarray:
        w, h = self.input_window, self.horizon
        # Aligned to make_windows targets: target index i uses value[i-h].
        return np.asarray(values[w - 1:len(values) - h], dtype=float)


class SeasonalNaiveForecaster:
    """yhat[t] = value[t - season] (one day earlier), else persistence."""

    horizon = C.LSTM_PARAMS["horizon"]
    input_window = C.LSTM_PARAMS["input_window"]
    season = C.SAMPLES_PER_DAY
    _fitted = True

    def __init__(self):
        self._train: np.ndarray | None = None

    def fit(self, train_values: np.ndarray):
        self._train = np.asarray(train_values, dtype=float)
        return self

    def predict_next(self, recent_values: np.ndarray) -> float:
        if len(recent_values) >= self.season:
            return float(recent_values[-self.season])
        return float(recent_values[-1])

    def predict_series(self, values: np.ndarray) -> np.ndarray:
        w, h = self.input_window, self.horizon
        out = []
        for i in range(w, len(values) - h + 1):
            if i - self.season >= 0:
                out.append(values[i - self.season])
            else:
                out.append(values[i - 1])
        return np.asarray(out, dtype=float)


def train_test_predict(values: np.ndarray, forecaster):
    """Mirror of models.traffic_predictor.train_test_predict for baselines."""
    from ..preprocessing import chronological_split
    w = forecaster.input_window
    h = forecaster.horizon
    train, test = chronological_split(values, C.LSTM_PARAMS["train_frac"])
    forecaster.fit(train)
    seed = np.concatenate([train[-w:], test])
    y_pred = forecaster.predict_series(seed)
    y_true = seed[w + h - 1:]
    m = min(len(y_true), len(y_pred))
    return y_true[:m], y_pred[:m], forecaster


if __name__ == "__main__":
    from ..data_loader import load_all
    from ..preprocessing import build_feature_frame

    s = load_all(sample=True)[0]
    vals = build_feature_frame(s)["value"].to_numpy()
    for name, f in [("persistence", PersistenceForecaster()),
                    ("seasonal_naive", SeasonalNaiveForecaster())]:
        yt, yp, _ = train_test_predict(vals, f)
        mae = float(np.mean(np.abs(yt - yp)))
        print(f"{name:<16}: test MAE={mae:.2f}  (n={len(yt)})")
