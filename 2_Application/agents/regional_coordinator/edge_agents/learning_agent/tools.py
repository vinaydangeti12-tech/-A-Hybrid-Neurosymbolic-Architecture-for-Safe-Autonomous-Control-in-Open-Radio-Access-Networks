"""Learning Agent tools — records outcomes and reports REAL model state.

This agent reflects how the H-TRACE core actually learns: the Isolation Forest
and the LSTM are trained OFFLINE (the research pipeline) and run in inference-only
mode at runtime, so there is no fabricated "live accuracy" here. Instead the agent
introspects the real fitted models in agents/htrace_core.py — their backend, fitted
status and hyperparameters — and logs action outcomes for the next offline retrain.
Reporting real state (never invented precision/recall) is itself part of the
anti-hallucination design.
"""

from datetime import datetime
from typing import Dict, List

import numpy as np

# Real H-TRACE core. Defensive import so the tool degrades to a clearly-labelled
# "core_unavailable" report rather than crashing.
try:
    from agents.htrace_core import CORE, IFOREST_PARAMS, LSTM_PARAMS
except Exception:  # pragma: no cover
    try:
        from htrace_core import CORE, IFOREST_PARAMS, LSTM_PARAMS
    except Exception:
        CORE = None
        IFOREST_PARAMS = {}
        LSTM_PARAMS = {}


def _real_model_state() -> Dict:
    """Introspect the real fitted models — facts only, nothing invented."""
    if CORE is None:
        return {"core_available": False}
    backend = CORE.backend
    buf = np.asarray(CORE.agent_buffer, dtype=float) if CORE.agent_buffer else np.array([])
    return {
        "core_available": True,
        "core_fitted": bool(backend.get("fitted")),
        "samples_in_buffer": int(buf.size),
        "buffer_mean": round(float(buf.mean()), 3) if buf.size else None,
        "buffer_std": round(float(buf.std()), 3) if buf.size else None,
        "anomaly_detector": {
            "algorithm": "IsolationForest",
            "backend": "scikit-learn",
            "fitted": bool(backend.get("sklearn")),
            "mode": "inference_only",
            "n_estimators": IFOREST_PARAMS.get("n_estimators"),
            "contamination": IFOREST_PARAMS.get("contamination"),
        },
        "traffic_forecaster": {
            "algorithm": "LSTM",
            "backend": "pytorch",
            "fitted": bool(backend.get("torch_lstm")),
            "mode": "inference_only",
            "input_window": LSTM_PARAMS.get("input_window"),
            "hidden_size": LSTM_PARAMS.get("hidden_size"),
            "epochs": LSTM_PARAMS.get("epochs"),
        },
    }


def record_action_outcome(action_id: str, action_type: str, success: bool, metrics: Dict) -> Dict:
    """
    Record the outcome of an action so it can feed the next OFFLINE retrain.
    No model weights are changed at runtime (the core is inference-only); the
    outcome is logged as a learning signal for the offline pipeline.

    Args:
        action_id: Unique action identifier
        action_type: 'trx_shutdown' | 'load_balance' | 'fault_isolation'
        success: Whether the action achieved its objective
        metrics: Measured KPIs after action (energy_saving_pct, cbp, mttr, etc.)
    """
    return {
        "action_id": action_id,
        "action_type": action_type,
        "success": success,
        "metrics": metrics,
        "recorded_at": datetime.now().isoformat(),
        "learning_signal": "positive" if success else "negative",
        "queued_for_offline_retrain": True,
        "runtime_weights_modified": False,  # honest: inference-only at runtime
        "model_state": _real_model_state(),
    }


def update_prediction_model(model_type: str, feedback_data: List[Dict]) -> Dict:
    """
    Summarise feedback and report the REAL current model state.
    The H-TRACE core trains offline and infers online, so this does NOT mutate
    live weights; it aggregates the feedback signal that the offline retrain
    (the research pipeline) would consume, and returns the real fitted state.

    Args:
        model_type: 'traffic_forecast' | 'anomaly_detector' | 'energy_optimiser'
        feedback_data: List of recent action outcome records
    """
    n_positive = sum(1 for f in feedback_data if f.get("learning_signal") == "positive")
    n_negative = len(feedback_data) - n_positive

    return {
        "model_type": model_type,
        "samples_processed": len(feedback_data),
        "positive_signals": n_positive,
        "negative_signals": n_negative,
        "net_signal": n_positive - n_negative,
        "training_mode": "offline_then_inference",
        "runtime_weights_modified": False,
        "queued_for_offline_retrain": len(feedback_data) > 0,
        "model_state": _real_model_state(),
        "updated_at": datetime.now().isoformat(),
    }


def get_performance_summary() -> Dict:
    """Report the REAL learning/model state of the H-TRACE core (no invented metrics)."""
    return {
        "timestamp": datetime.now().isoformat(),
        "training_paradigm": "offline training, online inference",
        "models": _real_model_state(),
        "note": ("Runtime is inference-only; precision/recall are measured offline "
                 "on the held-out validation set, not fabricated per-call."),
    }
