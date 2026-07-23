"""
H-TRACE child agent — a "Local Team" (Area A / Area B).

Pseudocode mapping (runs every few seconds, per area):
    WATCH   the live data
    SPOT    a fault            -> IsolationForestDetector
    PREDICT near-future load   -> LSTMPredictor
    DECIDE  the best action    -> deterministic policy below
    hand the action to the Safety Check

The agent is entirely **non-generative ML + fixed decision rules**, so every
action it emits is structurally valid by construction (0% hallucination). The
*safety* of each action is then independently verified by the SafetyGate.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .. import config as C
from .anomaly_detector import IsolationForestDetector
from .traffic_predictor import LSTMPredictor
from .safety_gate import Action, ActionType


# Operator intents the Smart Manager can hand down to a Local Team.
INTENT_SAVE_ENERGY = "save_energy"      # Night Mode
INTENT_MAX_CAPACITY = "max_capacity"    # Festival Mode
INTENT_HEAL = "heal"                    # Self-Healing


@dataclass
class AgentObservation:
    """One step of live telemetry handed to the agent."""
    recent_values: np.ndarray           # last K KPI samples (for prediction)
    feat_row: pd.DataFrame              # single-row feature frame (for detection)
    cell_id: str
    intent: str


@dataclass
class AgentOutput:
    action: Action
    fault_detected: bool
    anomaly_score: float
    predicted_load: float
    decision_latency_ms: float


class ChildAgent:
    """A per-area ML team: fault detection + traffic prediction + decision."""

    def __init__(self, area: str,
                 detector: IsolationForestDetector,
                 predictor: Optional[LSTMPredictor] = None):
        self.area = area
        self.detector = detector
        self.predictor = predictor

    # -- the live control step -------------------------------------------- #
    def step(self, obs: AgentObservation) -> AgentOutput:
        t0 = time.perf_counter()

        # SPOT — fault detection (unsupervised ML).
        score = float(self.detector.score(obs.feat_row)[0])
        flag = int(self.detector.predict(obs.feat_row)[0])
        fault = bool(flag)

        # PREDICT — near-future load (LSTM); fall back to last value if no model.
        if self.predictor is not None and getattr(self.predictor, "_fitted", False):
            pred = self.predictor.predict_next(obs.recent_values)
        else:
            pred = float(obs.recent_values[-1])
        pred = float(np.clip(pred, C.SAFETY_BOUNDS["load_min"],
                             C.SAFETY_BOUNDS["load_max"]))

        # DECIDE — deterministic policy conditioned on intent + ML outputs.
        action = self._decide(obs, fault, pred)

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return AgentOutput(action=action, fault_detected=fault,
                           anomaly_score=score, predicted_load=pred,
                           decision_latency_ms=latency_ms)

    # -- decision policy --------------------------------------------------- #
    def _decide(self, obs: AgentObservation, fault: bool, pred: float) -> Action:
        cell = obs.cell_id

        # 1) Faults always take priority -> mitigation (self-healing).
        if fault:
            atype = ActionType.REROUTE if pred > 200 else ActionType.RESTART
            return Action(type=atype, cell_id=cell, predicted_load=pred,
                          fault_active=True, source=f"{self.area}:ml")

        # 2) Otherwise act on the operator intent.
        if obs.intent == INTENT_SAVE_ENERGY:
            # Night Mode: sleep the cell only when the ML predicts low load.
            if pred <= C.SAFETY_BOUNDS["sleep_max_predicted_load"]:
                return Action(ActionType.SLEEP_CELL, cell, predicted_load=pred,
                              source=f"{self.area}:ml")
            return Action(ActionType.NO_OP, cell, predicted_load=pred,
                          source=f"{self.area}:ml")

        if obs.intent == INTENT_MAX_CAPACITY:
            # Festival Mode: keep the cell awake; scale power with predicted load.
            target_power = float(np.clip(pred / C.VALUE_SCALE * 100.0, 0, 100))
            if pred > 800:
                # Near saturation -> offload part of the load to a neighbour.
                return Action(ActionType.OFFLOAD, cell, predicted_load=pred,
                              offload_fraction=0.25,
                              offload_target_load=300.0,
                              source=f"{self.area}:ml")
            return Action(ActionType.SCALE_POWER, cell, predicted_load=pred,
                          power_pct=target_power, source=f"{self.area}:ml")

        # 3) Default / heal intent with no active fault.
        return Action(ActionType.NO_OP, cell, predicted_load=pred,
                      source=f"{self.area}:ml")


if __name__ == "__main__":
    from ..data_loader import load_all
    from ..preprocessing import build_feature_frame

    s = load_all(sample=True)[0]
    fdf = build_feature_frame(s)
    det = IsolationForestDetector().fit(fdf)
    agent = ChildAgent(area=s.area, detector=det, predictor=None)

    row = fdf.iloc[[5000]]
    obs = AgentObservation(recent_values=fdf["value"].to_numpy()[4988:5000],
                           feat_row=row, cell_id=s.series_id,
                           intent=INTENT_SAVE_ENERGY)
    out = agent.step(obs)
    print(f"action={out.action.type.value} pred={out.predicted_load:.1f} "
          f"fault={out.fault_detected} latency={out.decision_latency_ms:.3f}ms")
