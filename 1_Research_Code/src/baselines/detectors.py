"""
Baseline anomaly detectors (for comparison against H-TRACE's Isolation Forest).

All detectors expose the same interface as the H-TRACE detector
(`fit`, `score`, `predict`) so the evaluation harness can treat them uniformly:

  * ThresholdDetector — classic rolling-z-score statistical detector. The kind
    of lightweight rule that pre-ML O-RAN monitoring used.
  * OCSVMDetector     — One-Class SVM novelty detector (a standard ML baseline).

The **Tsourdinis et al. (ACM MobiCom 2024)** primary baseline uses an
Isolation Forest for 5G anomaly detection; H-TRACE reuses the same detector
family (`src.models.anomaly_detector.IsolationForestDetector`) but the *system*
wrapper differs: the Tsourdinis baseline has **no LSTM prediction layer, no
hierarchy and no Safety Gate** — its actions execute directly. That wiring lives
in the experiment runner; this module supplies the alternative detectors.
"""
from __future__ import annotations

import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from .. import config as C
from ..preprocessing import ANOMALY_FEATURES


class ThresholdDetector:
    """Rolling-z-score detector: |value - roll_mean| / roll_std > k."""

    def __init__(self, contamination: float | None = None):
        # Operate at the same alert rate as the other detectors for fairness.
        self.contamination = contamination or C.IFOREST_PARAMS["contamination"]
        self.k = 3.0
        self._fitted = False

    @staticmethod
    def _zscore(feat_df) -> np.ndarray:
        return (np.abs(feat_df["residual"].to_numpy())
                / (feat_df["roll_std"].to_numpy() + 1e-6))

    def fit(self, feat_df) -> "ThresholdDetector":
        # Calibrate the threshold to the (1 - contamination) quantile of the
        # training z-scores, so the operating point matches the ML detectors.
        z = self._zscore(feat_df)
        self.k = float(np.quantile(z, 1.0 - self.contamination))
        self._zmax = float(z.max()) or 1.0
        self._fitted = True
        return self

    def score(self, feat_df) -> np.ndarray:
        z = self._zscore(feat_df)
        return 1.0 - 1.0 / (1.0 + z)            # squash to [0,1), monotonic in z

    def predict(self, feat_df) -> np.ndarray:
        return (self._zscore(feat_df) > self.k).astype(int)


class OCSVMDetector:
    """One-Class SVM novelty detector over the same engineered features."""

    def __init__(self, nu: float = 0.02, gamma: str = "scale"):
        self.model = OneClassSVM(nu=nu, gamma=gamma, kernel="rbf")
        self.scaler = StandardScaler()
        self._fitted = False

    def fit(self, feat_df) -> "OCSVMDetector":
        # OCSVM is O(n^2); subsample for tractable fitting on long series.
        X = self.scaler.fit_transform(feat_df[ANOMALY_FEATURES].to_numpy())
        if len(X) > 3000:
            rng = np.random.default_rng(C.RANDOM_SEED)
            X = X[rng.choice(len(X), 3000, replace=False)]
        self.model.fit(X)
        self._fitted = True
        return self

    def score(self, feat_df) -> np.ndarray:
        X = self.scaler.transform(feat_df[ANOMALY_FEATURES].to_numpy())
        raw = -self.model.decision_function(X)
        lo, hi = raw.min(), raw.max()
        return (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)

    def predict(self, feat_df) -> np.ndarray:
        X = self.scaler.transform(feat_df[ANOMALY_FEATURES].to_numpy())
        return (self.model.predict(X) == -1).astype(int)


if __name__ == "__main__":
    from ..data_loader import load_all
    from ..preprocessing import build_feature_frame

    s = [s for s in load_all(sample=True) if s.incidents][0]
    fdf = build_feature_frame(s)
    labels = fdf["is_anomaly"].to_numpy()
    for name, det in [("threshold", ThresholdDetector()), ("ocsvm", OCSVMDetector())]:
        det.fit(fdf)
        flags = det.predict(fdf)
        hit = int((flags & labels).sum())
        print(f"{name:<10}: {flags.sum()} flagged ({100*flags.mean():.2f}%), "
              f"{hit}/{labels.sum()} labelled fault samples detected.")
