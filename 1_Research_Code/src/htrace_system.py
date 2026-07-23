"""
System wrappers used for a like-for-like comparison.

Every competing approach is expressed as a `System`. Because episodes span many
series, a System does not hold a single fitted model; instead it names which
*per-series* model registry to use:

    System(name, detector_key, use_forecaster, use_gate)

  * H-TRACE (full)       : IsolationForest + LSTM + Safety Gate = ON
  * H-TRACE NoGate (abl.): IsolationForest + LSTM + Safety Gate = OFF
  * Tsourdinis (baseline): IsolationForest + (no forecaster) + Gate OFF
  * OCSVM (baseline)     : One-Class SVM + (no forecaster) + Gate OFF
  * Threshold (baseline) : rolling-z-score + (no forecaster) + Gate OFF

The shared decision policy lives in `ChildAgent`; the only structural difference
that drives the safety results is whether actions must pass the deterministic
Safety Gate before "execution". This isolates the contribution of H-TRACE's
symbolic safety layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models.child_agent import ChildAgent
from .models.safety_gate import Action, GateDecision, SafetyGate
from .models.smart_manager import SmartManager


@dataclass
class ExecResult:
    action: Action
    executed: bool
    gate_decision: Optional[GateDecision]


@dataclass
class System:
    name: str
    short: str
    detector_key: str                 # key into the detector registry
    use_forecaster: bool = False      # use the per-series LSTM?
    use_gate: bool = False
    gate: SafetyGate = field(default_factory=SafetyGate)
    manager: SmartManager = field(default_factory=SmartManager)

    def make_agent(self, area: str, detector, forecaster) -> ChildAgent:
        return ChildAgent(area=area, detector=detector,
                          predictor=forecaster if self.use_forecaster else None)

    def execute(self, action: Action) -> ExecResult:
        """
        Apply the action to the (simulated) equipment.

        With the Safety Gate ON, only approved actions execute. With the gate
        OFF (every baseline), the action executes directly — exactly the gap
        H-TRACE closes.
        """
        if self.use_gate:
            decision = self.gate.check(action)
            if decision.blocked:
                self.manager.on_gate_decision(action.source, decision)
            return ExecResult(action, decision.approved, decision)
        # No safety mechanism: the action reaches the equipment unchecked.
        return ExecResult(action, True, None)


def default_systems() -> list[System]:
    """The full comparison set for the evaluation experiment."""
    return [
        System("H-TRACE (full)", "H-TRACE", "iforest",
               use_forecaster=True, use_gate=True),
        System("H-TRACE NoGate (ablation)", "H-TRACE-NoGate", "iforest",
               use_forecaster=True, use_gate=False),
        System("Tsourdinis et al. (MobiCom'24)", "Tsourdinis", "iforest",
               use_forecaster=False, use_gate=False),
        System("OCSVM baseline", "OCSVM", "ocsvm",
               use_forecaster=False, use_gate=False),
        System("Threshold baseline", "Threshold", "threshold",
               use_forecaster=False, use_gate=False),
    ]
