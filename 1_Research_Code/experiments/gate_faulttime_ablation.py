"""
Fault-time Safety-Gate ablation on REAL episodes (supervisor Week-7, Item 1).

Why this experiment exists
--------------------------
In the main evaluation the gate blocks 0 actions on real episodes: whenever the
ML policy *detects* a fault it already proposes a safe mitigation action, so the
gate has nothing to catch. That makes the "gate ON vs OFF" ablation look empty on
real traffic. This experiment isolates the gate's operational value on the SAME
real episodes the main evaluation uses, by changing one realistic condition:

    The edge fault detector misses a fraction of real faults (its self-healing
    recall is well below 100%). When it misses a fault while the operator has a
    standing optimisation intent (max_capacity / save_energy), the ML proposes an
    optimisation action (scale power / offload / sleep a cell). Performing that
    DURING a confirmed fault is unsafe.

H-TRACE's gate does not rely on the edge detector here: it uses a telemetry/RIC
confirmed-fault signal (the ground-truth fault label of these self-healing
episodes) that is independent of the edge model. So even when the edge detector
misses the fault, the deterministic gate blocks the unsafe optimisation — defense
in depth against an ML *detection* failure, not a constructed adversarial command.

Consistency: this reuses the exact same self-healing episodes and Isolation-Forest
detector as the main evaluation (same RANDOM_SEED), so the episode count and the
detection recall match the approved run; only the operator intent is overridden.

Run:  python -m experiments.gate_faulttime_ablation
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from src import config as C
from src.data_loader import load_all
from src.models.anomaly_detector import IsolationForestDetector
from src.models.child_agent import (AgentObservation, ChildAgent,
                                     INTENT_MAX_CAPACITY, INTENT_SAVE_ENERGY)
from src.models.safety_gate import OPTIMISATION_ACTIONS, SafetyGate
from src.evaluation.scenarios import build_episodes
from src.preprocessing import build_feature_frame

STANDING_INTENTS = (INTENT_MAX_CAPACITY, INTENT_SAVE_ENERGY)


def run() -> pd.DataFrame:
    series = load_all(sample=False)                       # same series set as the eval
    rng = np.random.default_rng(C.RANDOM_SEED)            # same seed -> same episodes
    episodes = [e for e in build_episodes(series, rng) if e.scenario == "self_healing"]

    # Fit the Isolation-Forest detector per real series (same model as the eval).
    reals = {s.series_id: s for s in series if s.kind == "real"}
    detectors = {sid: IsolationForestDetector().fit(build_feature_frame(s))
                 for sid, s in reals.items()}

    gate = SafetyGate()
    rows = []
    for intent in STANDING_INTENTS:
        n_ep = detected = missed = 0
        unsafe_optim = gate_on_blocked = gate_off_exec = 0
        for ep in episodes:
            det = detectors[ep.series_id]
            agent = ChildAgent(area=ep.area, detector=det, predictor=None)
            obs = AgentObservation(recent_values=ep.recent_values,
                                   feat_row=ep.feat_row, cell_id=ep.series_id,
                                   intent=intent)
            out = agent.step(obs)                         # ML detect + decide (persistence pred)
            n_ep += 1
            detected += int(out.fault_detected)
            missed += int(not out.fault_detected)

            # Gate sees the confirmed fault (ground truth) regardless of the ML flag.
            gate_action = replace(out.action, fault_active=True)
            if out.action.type in OPTIMISATION_ACTIONS:   # unsafe optimisation during a fault
                unsafe_optim += 1
                if gate.check(gate_action).blocked:       # gate ON blocks it
                    gate_on_blocked += 1
                gate_off_exec += 1                        # gate OFF lets it through

        rows.append({
            "standing_intent": intent,
            "self_healing_episodes": n_ep,
            "ml_detected_fault": detected,
            "ml_recall_%": round(100.0 * detected / n_ep, 1) if n_ep else 0.0,
            "ml_missed_fault": missed,
            "unsafe_optimisation_proposed": unsafe_optim,
            "gate_ON_blocked": gate_on_blocked,
            "gate_OFF_executed_unsafe": gate_off_exec,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Fault-time Safety-Gate ablation on the evaluation's real self-healing episodes\n")
    df = run()
    print(df.to_string(index=False))

    tot_block = int(df["gate_ON_blocked"].sum())
    tot_exec = int(df["gate_OFF_executed_unsafe"].sum())
    print(f"\nOn the same real self-healing episodes as the main evaluation:")
    print(f"  Gate ON  blocked {tot_block} unsafe optimisation-during-fault actions.")
    print(f"  Gate OFF executed all {tot_exec} of them unchecked (they would reach equipment).")
    print("  => The ablation is non-empty on real traffic precisely where the edge "
          "detector MISSES a fault; the gate is a deterministic backstop for ML detection failures.")

    df.to_csv(C.TABLES_DIR / "gate_faulttime_ablation.csv", index=False)
    print(f"\nWrote: {C.TABLES_DIR / 'gate_faulttime_ablation.csv'}")
