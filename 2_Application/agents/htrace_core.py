"""
H-TRACE real core — the actual ML + deterministic Safety Gate used by the app.

This module makes the interactive application FOLLOW THE H-TRACE ARCHITECTURE
instead of only drawing it:

    Smart Manager (AI, elsewhere)
        -> Local Team  (real non-generative ML)
             SPOT    : sklearn IsolationForest  (anomaly detection)
             PREDICT : torch LSTM               (traffic forecast)
             DECIDE  : deterministic policy      -> a structured Action
        -> Safety Gate (deterministic rules, NOT AI) -> approve / block
        -> Equipment

It is intentionally self-contained (no dependency on 1_Research_Code) so the
application package runs on its own, but it mirrors the research implementation
in src/models/*. Heavy bits (sklearn/torch) degrade gracefully: if a model is
not yet fitted, the core falls back to a safe deterministic stand-in so the
running app can never crash.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, List, Optional

import numpy as np

# Optional heavy deps — degrade gracefully if unavailable.
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    _SKLEARN = True
except Exception:                                    # pragma: no cover
    _SKLEARN = False

try:
    import torch
    import torch.nn as nn
    _TORCH = True
except Exception:                                    # pragma: no cover
    _TORCH = False


# ===========================================================================
# Configuration (mirrors 1_Research_Code/src/config.py — kept in sync by value)
# ===========================================================================
VALUE_SCALE = 1000.0
ROLLING_WINDOW = 12
RANDOM_SEED = 42

IFOREST_PARAMS = dict(n_estimators=200, contamination=0.02,
                      max_samples="auto", random_state=RANDOM_SEED, n_jobs=1)

LSTM_PARAMS = dict(input_window=24, hidden_size=48, num_layers=1,
                   dropout=0.0, lr=1e-3, epochs=12, batch_size=128)

SAFETY_BOUNDS = dict(
    sleep_max_predicted_load=300.0,
    power_min_pct=0.0, power_max_pct=100.0,
    neighbor_capacity=1000.0, max_offload_fraction=0.8,
    load_min=0.0, load_max=1000.0,
    block_optimisation_during_fault=True,
)

# Operator intents handed down by the Smart Manager.
INTENT_SAVE_ENERGY = "save_energy"
INTENT_MAX_CAPACITY = "max_capacity"
INTENT_HEAL = "heal"


# ===========================================================================
# Tier 3 — Safety Gate (deterministic, rule-based; NOT AI)
# Ported from src/models/safety_gate.py
# ===========================================================================
class ActionType(str, Enum):
    SLEEP_CELL = "sleep_cell"
    WAKE_CELL = "wake_cell"
    SCALE_POWER = "scale_power"
    OFFLOAD = "offload"
    REROUTE = "reroute"
    RESTART = "restart"
    NO_OP = "no_op"


MITIGATION_ACTIONS = {ActionType.REROUTE, ActionType.RESTART, ActionType.NO_OP}
OPTIMISATION_ACTIONS = {ActionType.SLEEP_CELL, ActionType.WAKE_CELL,
                        ActionType.SCALE_POWER, ActionType.OFFLOAD}


@dataclass
class Action:
    type: ActionType
    cell_id: str = "cell_0"
    predicted_load: float = 0.0
    power_pct: Optional[float] = None
    offload_fraction: Optional[float] = None
    offload_target_load: Optional[float] = None
    fault_active: bool = False
    source: str = "ml"

    def is_wellformed(self) -> bool:
        """Schema/type validity — the anti-hallucination structural check."""
        if not isinstance(self.type, ActionType):
            return False
        for num in (self.predicted_load, self.power_pct, self.offload_fraction,
                    self.offload_target_load):
            if num is not None and (num != num):            # NaN
                return False
        if self.type == ActionType.SCALE_POWER and self.power_pct is None:
            return False
        if self.type == ActionType.OFFLOAD and (
                self.offload_fraction is None or self.offload_target_load is None):
            return False
        return True


@dataclass
class GateDecision:
    approved: bool
    action: Action
    reasons: List[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return not self.approved


class SafetyGate:
    """Deterministic rule engine. Every rule is an absolute boundary check."""

    def __init__(self, bounds: dict | None = None):
        self.b = {**SAFETY_BOUNDS, **(bounds or {})}

    def check(self, action: Action) -> GateDecision:
        reasons: List[str] = []
        b = self.b

        # Rule 0 — structural well-formedness (anti-hallucination).
        if not action.is_wellformed():
            return GateDecision(False, action, ["malformed_or_invalid_action"])

        # Rule 1 — predicted load must be physically possible.
        if not (b["load_min"] <= action.predicted_load <= b["load_max"]):
            reasons.append("predicted_load_out_of_range")

        # Rule 2 — never sleep a cell that is (predicted to be) busy.
        if action.type == ActionType.SLEEP_CELL:
            if action.predicted_load > b["sleep_max_predicted_load"]:
                reasons.append("sleep_blocked_high_predicted_load")

        # Rule 3 — power/capacity must stay within hardware limits.
        if action.type == ActionType.SCALE_POWER:
            if not (b["power_min_pct"] <= (action.power_pct or 0) <= b["power_max_pct"]):
                reasons.append("power_out_of_bounds")

        # Rule 4 — offloading must not overload the neighbour cell.
        if action.type == ActionType.OFFLOAD:
            if not (0.0 <= (action.offload_fraction or 0) <= 1.0):
                reasons.append("offload_fraction_invalid")
            projected = ((action.offload_target_load or 0)
                         + (action.offload_fraction or 0) * action.predicted_load)
            cap_limit = b["max_offload_fraction"] * b["neighbor_capacity"]
            if projected > cap_limit:
                reasons.append("offload_would_overload_neighbor")

        # Rule 5 — during an active confirmed fault, only mitigation is allowed.
        if b["block_optimisation_during_fault"] and action.fault_active:
            if action.type in OPTIMISATION_ACTIONS:
                reasons.append("optimisation_blocked_during_active_fault")

        return GateDecision(len(reasons) == 0, action, reasons)


# ===========================================================================
# Tier 2a — SPOT: Isolation Forest fault detector (real sklearn, online)
# ===========================================================================
class IsolationForestDetector:
    """Unsupervised fault detector over rolling-statistic features."""

    def __init__(self, **params):
        self.params = {**IFOREST_PARAMS, **params}
        self.model = IsolationForest(**self.params) if _SKLEARN else None
        self.scaler = StandardScaler() if _SKLEARN else None
        self._fitted = False
        self._raw_lo = 0.0
        self._raw_hi = 1.0

    @staticmethod
    def _features(values: np.ndarray) -> np.ndarray:
        """[value, roll_mean, roll_std, value-roll_mean, abs_diff] per sample."""
        v = np.asarray(values, dtype=float)
        n = len(v)
        feats = np.zeros((n, 5), dtype=float)
        for i in range(n):
            lo = max(0, i - ROLLING_WINDOW + 1)
            window = v[lo:i + 1]
            rm = float(window.mean())
            rs = float(window.std())
            diff = abs(v[i] - v[i - 1]) if i > 0 else 0.0
            feats[i] = [v[i], rm, rs, v[i] - rm, diff]
        return feats

    @staticmethod
    def _features_last(values: np.ndarray) -> np.ndarray:
        """Features for ONLY the most recent sample — O(window), used at inference.

        Avoids rebuilding the whole feature matrix every tick (the buffer can be
        thousands of samples long); only the last row is needed to score now.
        """
        v = np.asarray(values, dtype=float)
        window = v[-ROLLING_WINDOW:]
        rm = float(window.mean())
        rs = float(window.std())
        diff = abs(v[-1] - v[-2]) if len(v) > 1 else 0.0
        return np.array([[v[-1], rm, rs, v[-1] - rm, diff]], dtype=float)

    def fit(self, values: np.ndarray) -> "IsolationForestDetector":
        if not _SKLEARN or len(values) < ROLLING_WINDOW + 5:
            self._fitted = False
            return self
        X = self._features(values)
        Xs = self.scaler.fit_transform(X)
        self.model.fit(Xs)
        raw = -self.model.decision_function(Xs)
        self._raw_lo, self._raw_hi = float(raw.min()), float(raw.max())
        self._fitted = True
        return self

    def score_window(self, recent_values: np.ndarray) -> tuple[float, bool]:
        """Return (anomaly_score in [0,1], is_fault) for the latest sample.

        Falls back to a deterministic z-score stand-in if not fitted, so the
        app keeps working before/without a trained model.
        """
        v = np.asarray(recent_values, dtype=float)
        if len(v) == 0:
            return 0.0, False
        if not (self._fitted and _SKLEARN):
            # Deterministic fallback: rolling z-score normalised to [0,1].
            w = v[-ROLLING_WINDOW:]
            mu, sd = float(w.mean()), float(w.std()) or 1.0
            z = abs(v[-1] - mu) / sd
            return float(min(1.0, z / 4.0)), bool(z > 3.0)
        X = self._features_last(v)
        Xs = self.scaler.transform(X)
        raw = float(-self.model.decision_function(Xs)[0])
        span = (self._raw_hi - self._raw_lo) or 1.0
        score = (raw - self._raw_lo) / span
        flag = bool(self.model.predict(Xs)[0] == -1)
        return float(max(0.0, min(1.0, score))), flag


# ===========================================================================
# Tier 2b — PREDICT: LSTM traffic forecaster (real torch, with fallback)
# ===========================================================================
if _TORCH:
    class _LSTMNet(nn.Module):
        def __init__(self, hidden_size: int, num_layers: int, dropout: float):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=hidden_size,
                                num_layers=num_layers, batch_first=True,
                                dropout=dropout if num_layers > 1 else 0.0)
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)


class LSTMForecaster:
    """Per-stream LSTM forecaster (real torch). Falls back to persistence."""

    def __init__(self, **params):
        self.p = {**LSTM_PARAMS, **params}
        self.net = (_LSTMNet(self.p["hidden_size"], self.p["num_layers"],
                             self.p["dropout"]) if _TORCH else None)
        self._lo = 0.0
        self._hi = 1.0
        self._fitted = False

    def _scale(self, a):
        span = (self._hi - self._lo) or 1.0
        return (np.asarray(a, dtype=float) - self._lo) / span

    def _unscale(self, a):
        return np.asarray(a, dtype=float) * ((self._hi - self._lo) or 1.0) + self._lo

    def fit(self, values: np.ndarray) -> "LSTMForecaster":
        w = self.p["input_window"]
        if not _TORCH or len(values) < w + 10:
            self._fitted = False
            return self
        torch.manual_seed(RANDOM_SEED)
        self._lo, self._hi = float(np.min(values)), float(np.max(values))
        v = self._scale(values)
        X = np.stack([v[i:i + w] for i in range(len(v) - w)])
        y = v[w:]
        Xt = torch.tensor(X[..., None], dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.float32)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.p["lr"])
        loss_fn = nn.MSELoss()
        bs = self.p["batch_size"]
        self.net.train()
        for _ in range(self.p["epochs"]):
            perm = torch.randperm(len(Xt))
            for i in range(0, len(Xt), bs):
                idx = perm[i:i + bs]
                opt.zero_grad()
                loss = loss_fn(self.net(Xt[idx]), yt[idx])
                loss.backward()
                opt.step()
        self._fitted = True
        return self

    def predict_next(self, recent_values: np.ndarray) -> float:
        v = np.asarray(recent_values, dtype=float)
        if len(v) == 0:
            return 0.0
        if not (self._fitted and _TORCH):
            return float(v[-1])                              # persistence fallback
        w = self.p["input_window"]
        window = v[-w:]
        if len(window) < w:
            window = np.concatenate([np.full(w - len(window), window[0]), window])
        x = torch.tensor(self._scale(window)[None, :, None], dtype=torch.float32)
        self.net.eval()
        with torch.no_grad():
            yhat = float(self.net(x).item())
        return float(self._unscale([yhat])[0])


# ===========================================================================
# Tier 2c — DECIDE policy (deterministic) + Local Team orchestration
# Ported from src/models/child_agent.py
# ===========================================================================
def decide(intent: str, fault: bool, pred: float, cell_id: str,
           area: str = "Area_A") -> Action:
    src = f"{area}:ml"
    if fault:
        atype = ActionType.REROUTE if pred > 200 else ActionType.RESTART
        return Action(atype, cell_id, predicted_load=pred, fault_active=True, source=src)
    if intent == INTENT_SAVE_ENERGY:
        if pred <= SAFETY_BOUNDS["sleep_max_predicted_load"]:
            return Action(ActionType.SLEEP_CELL, cell_id, predicted_load=pred, source=src)
        return Action(ActionType.NO_OP, cell_id, predicted_load=pred, source=src)
    if intent == INTENT_MAX_CAPACITY:
        if pred > 800:
            return Action(ActionType.OFFLOAD, cell_id, predicted_load=pred,
                          offload_fraction=0.25, offload_target_load=300.0, source=src)
        target_power = float(np.clip(pred / VALUE_SCALE * 100.0, 0, 100))
        return Action(ActionType.SCALE_POWER, cell_id, predicted_load=pred,
                      power_pct=target_power, source=src)
    return Action(ActionType.NO_OP, cell_id, predicted_load=pred, source=src)


@dataclass
class StepResult:
    anomaly_score: float          # [0, 1]
    fault_detected: bool
    predicted_load: float         # [0, 1000]
    action: Action
    gate: GateDecision
    latency_ms: float

    def as_dict(self) -> dict:
        return {
            "anomaly_score": round(self.anomaly_score, 4),
            "fault_detected": self.fault_detected,
            "predicted_load": round(self.predicted_load, 2),
            "action": self.action.type.value,
            "safety_gate": {
                "approved": self.gate.approved,
                "blocked": self.gate.blocked,
                "reasons": self.gate.reasons,
                "deterministic": True,
            },
            "decision_latency_ms": round(self.latency_ms, 3),
        }


class HTraceCore:
    """A real Local Team + Safety Gate the application can call each tick."""

    def __init__(self):
        self.detector = IsolationForestDetector()
        self.forecaster = LSTMForecaster()
        self.gate = SafetyGate()
        # Two independent rolling buffers so the live dashboard stream and the
        # ADK edge-agent tool calls don't pollute each other's context. The
        # trained models are shared (fitted once); a lock serialises all access
        # because sklearn/torch inference + the deques are touched from both the
        # SocketIO stream thread and request threads.
        self.buffer: Deque[float] = deque(maxlen=2048)        # scenario/stream path
        self.agent_buffer: Deque[float] = deque(maxlen=2048)  # ADK edge-agent path
        self._lock = threading.Lock()
        self.fitted = False

    @property
    def backend(self) -> dict:
        return {
            "sklearn": _SKLEARN and self.detector._fitted,
            "torch_lstm": _TORCH and self.forecaster._fitted,
            "fitted": self.fitted,
        }

    def fit(self, values) -> "HTraceCore":
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        if len(values) >= ROLLING_WINDOW + 10:
            with self._lock:
                self.detector.fit(values)
                self.forecaster.fit(values)
                seed = values[-self.forecaster.p["input_window"]:]
                self.buffer.extend(seed)
                self.agent_buffer.extend(seed)
                self.fitted = True
        return self

    # -- single-purpose helpers the ADK edge-agent tools call ---------------- #
    def detect(self, kpi_value: float) -> tuple[float, bool]:
        """SPOT: push a sample and return (anomaly_score in [0,1], is_fault)."""
        with self._lock:
            self.agent_buffer.append(float(kpi_value))
            return self.detector.score_window(np.asarray(self.agent_buffer, dtype=float))

    def forecast(self) -> float:
        """PREDICT: next-step load from the current buffer (0 if empty)."""
        with self._lock:
            if not self.agent_buffer:
                return 0.0
            pred = self.forecaster.predict_next(np.asarray(self.agent_buffer, dtype=float))
        return float(np.clip(pred, SAFETY_BOUNDS["load_min"], SAFETY_BOUNDS["load_max"]))

    def step(self, kpi_value: float, intent: str, cell_id: str = "cell_0",
             fault_hint: bool = False, use_ml_fault: bool = True,
             area: str = "Area_A") -> StepResult:
        """One real-time control step: SPOT -> PREDICT -> DECIDE -> GATE.

        The anomaly *score* is always the real ML output. ``use_ml_fault``
        controls whether an ML fault flag forces the mitigation path: enable it
        for self-healing, disable it for energy/capacity scenarios that have no
        injected fault (so a benign ML false-positive doesn't hijack the loop).
        """
        t0 = time.perf_counter()
        with self._lock:
            self.buffer.append(float(kpi_value))
            recent = np.asarray(self.buffer, dtype=float)
            score, fault_ml = self.detector.score_window(recent)
            pred = self.forecaster.predict_next(recent)

        fault = bool((fault_ml and use_ml_fault) or fault_hint)
        pred = float(np.clip(pred, SAFETY_BOUNDS["load_min"], SAFETY_BOUNDS["load_max"]))

        action = decide(intent, fault, pred, cell_id, area)
        decision = self.gate.check(action)

        latency = (time.perf_counter() - t0) * 1000.0
        return StepResult(score, fault, pred, action, decision, latency)


# Process-wide singleton the app imports.
CORE = HTraceCore()
