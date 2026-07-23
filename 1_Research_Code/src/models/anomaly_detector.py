"""
H-TRACE child-agent component #1 — Fault / anomaly detector.

Pseudocode mapping:  "SPOT anything that looks unusual (a fault)".

Implemented with an **unsupervised Isolation Forest** over rolling-statistic
features, exactly as specified in the Gap Analysis (non-generative traditional
ML at the edge -> 0% control-loop hallucination). Being deterministic and
purely numeric, its output is always a well-formed score; it can never emit a
malformed command (no hallucination surface).
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .. import config as C
from ..preprocessing import ANOMALY_FEATURES


class IsolationForestDetector:
    """Unsupervised fault detector (H-TRACE edge ML)."""

    def __init__(self, **params):
        self.params = {**C.IFOREST_PARAMS, **params}
        self.model = IsolationForest(**self.params)
        self.scaler = StandardScaler()
        self._fitted = False

    # -- training ---------------------------------------------------------- #
    def fit(self, feat_df) -> "IsolationForestDetector":
        X = self.scaler.fit_transform(feat_df[ANOMALY_FEATURES].to_numpy())
        self.model.fit(X)
        # Single-sample edge inference: avoid per-call thread-pool spawn so the
        # measured decision latency reflects the real Near-RT RIC control loop.
        self.model.n_jobs = 1
        self._fitted = True
        return self

    # -- inference --------------------------------------------------------- #
    def score(self, feat_df) -> np.ndarray:
        """Anomaly score in [0, 1] (higher = more anomalous)."""
        if not self._fitted:
            raise RuntimeError("Detector not fitted.")
        X = self.scaler.transform(feat_df[ANOMALY_FEATURES].to_numpy())
        # decision_function: higher = more normal -> negate & min-max to [0,1].
        raw = -self.model.decision_function(X)
        lo, hi = raw.min(), raw.max()
        return (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)

    def predict(self, feat_df) -> np.ndarray:
        """Binary fault flag (1 = anomaly) using the model's own threshold."""
        if not self._fitted:
            raise RuntimeError("Detector not fitted.")
        X = self.scaler.transform(feat_df[ANOMALY_FEATURES].to_numpy())
        return (self.model.predict(X) == -1).astype(int)


if __name__ == "__main__":
    from ..data_loader import load_all
    from ..preprocessing import build_feature_frame

    # Sanity check: detector should fire inside a known fault window.
    series = [s for s in load_all(sample=True) if s.incidents][0]
    fdf = build_feature_frame(series)
    det = IsolationForestDetector().fit(fdf)
    flags = det.predict(fdf)
    labels = fdf["is_anomaly"].to_numpy()
    fired_in_window = int((flags & labels).sum())
    print(f"{series.series_id}: predicted {flags.sum()} anomalies "
          f"({100*flags.mean():.2f}%); {fired_in_window}/{labels.sum()} "
          f"labelled fault samples detected.")
