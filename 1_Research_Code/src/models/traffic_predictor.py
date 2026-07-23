"""
H-TRACE child-agent component #2 — Traffic predictor.

Pseudocode mapping:  "PREDICT how busy the area will get soon".

A small **LSTM** (PyTorch) forecasting the next KPI sample from the last
`input_window` samples. This is the predictive layer H-TRACE adds on top of the
Tsourdinis-style anomaly-detection baseline. Output is a bounded numeric value,
so — like the detector — it has no hallucination surface.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from .. import config as C
from ..preprocessing import Scaler, make_windows, chronological_split

torch.manual_seed(C.RANDOM_SEED)
np.random.seed(C.RANDOM_SEED)


class _LSTMNet(nn.Module):
    def __init__(self, hidden_size: int, num_layers: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1, hidden_size=hidden_size, num_layers=num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x):                       # x: (B, W, 1)
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)   # (B,)


class LSTMPredictor:
    """Per-series LSTM traffic forecaster (H-TRACE edge ML)."""

    def __init__(self, **params):
        self.p = {**C.LSTM_PARAMS, **params}
        self.scaler: Scaler | None = None
        self.net = _LSTMNet(self.p["hidden_size"], self.p["num_layers"],
                            self.p["dropout"])
        self.device = torch.device("cpu")
        self.history: list[float] = []
        self._fitted = False

    # -- training ---------------------------------------------------------- #
    def fit(self, train_values: np.ndarray, verbose: bool = False) -> "LSTMPredictor":
        self.scaler = Scaler(float(train_values.min()), float(train_values.max()))
        v = self.scaler.transform(train_values)
        X, y = make_windows(v, self.p["input_window"], self.p["horizon"])
        if len(X) == 0:
            self._fitted = True
            return self
        X = torch.tensor(X[..., None], dtype=torch.float32)
        y = torch.tensor(y, dtype=torch.float32)

        opt = torch.optim.Adam(self.net.parameters(), lr=self.p["lr"])
        loss_fn = nn.MSELoss()
        bs = self.p["batch_size"]
        self.net.train()
        for epoch in range(self.p["epochs"]):
            perm = torch.randperm(len(X))
            ep_loss = 0.0
            for i in range(0, len(X), bs):
                idx = perm[i:i + bs]
                opt.zero_grad()
                pred = self.net(X[idx])
                loss = loss_fn(pred, y[idx])
                loss.backward()
                opt.step()
                ep_loss += loss.item() * len(idx)
            ep_loss /= len(X)
            self.history.append(ep_loss)
            if verbose:
                print(f"  epoch {epoch+1:02d}/{self.p['epochs']}  mse={ep_loss:.5f}")
        self._fitted = True
        return self

    # -- inference --------------------------------------------------------- #
    def predict_next(self, recent_values: np.ndarray) -> float:
        """Predict the next KPI value given the most recent window."""
        if not self._fitted or self.scaler is None:
            raise RuntimeError("Predictor not fitted.")
        w = self.p["input_window"]
        window = np.asarray(recent_values[-w:], dtype=np.float32)
        if len(window) < w:                      # left-pad short windows
            window = np.concatenate([np.full(w - len(window), window[0]), window])
        v = self.scaler.transform(window)
        x = torch.tensor(v[None, :, None], dtype=torch.float32)
        self.net.eval()
        with torch.no_grad():
            yhat = self.net(x).item()
        return float(self.scaler.inverse(np.array([yhat]))[0])

    def predict_series(self, values: np.ndarray) -> np.ndarray:
        """One-step-ahead predictions aligned to each target index."""
        if not self._fitted or self.scaler is None:
            raise RuntimeError("Predictor not fitted.")
        w, h = self.p["input_window"], self.p["horizon"]
        v = self.scaler.transform(values)
        X, _ = make_windows(v, w, h)
        if len(X) == 0:
            return np.array([])
        x = torch.tensor(X[..., None], dtype=torch.float32)
        self.net.eval()
        with torch.no_grad():
            yhat = self.net(x).numpy()
        return self.scaler.inverse(yhat)


def train_test_predict(values: np.ndarray, **params):
    """Convenience: chronological split -> train -> predict on the test tail.

    Returns (y_true, y_pred, predictor).
    """
    p = {**C.LSTM_PARAMS, **params}
    train, test = chronological_split(values, p["train_frac"])
    model = LSTMPredictor(**params).fit(train)
    w, h = p["input_window"], p["horizon"]
    # Use the last `w` train samples to seed predictions over the test region.
    seed = np.concatenate([train[-w:], test])
    y_pred = model.predict_series(seed)
    y_true = seed[w + h - 1:]
    m = min(len(y_true), len(y_pred))
    return y_true[:m], y_pred[:m], model


if __name__ == "__main__":
    from ..data_loader import load_all
    from ..preprocessing import build_feature_frame

    s = load_all(sample=True)[0]
    vals = build_feature_frame(s)["value"].to_numpy()
    y_true, y_pred, model = train_test_predict(vals, epochs=8)
    mae = np.mean(np.abs(y_true - y_pred))
    naive = np.mean(np.abs(np.diff(y_true)))      # persistence baseline MAE
    print(f"{s.series_id}: LSTM test MAE={mae:.2f} vs persistence MAE={naive:.2f}")
    print(f"  final train MSE={model.history[-1]:.5f}  (loss decreasing: "
          f"{model.history[0]:.4f} -> {model.history[-1]:.4f})")
