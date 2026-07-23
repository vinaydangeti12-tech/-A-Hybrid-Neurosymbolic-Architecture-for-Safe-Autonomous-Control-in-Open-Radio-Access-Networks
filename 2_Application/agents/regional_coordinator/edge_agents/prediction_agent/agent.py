"""Prediction Agent — non-generative ML child agent (LSTM forecaster).

A deterministic ADK ``BaseAgent`` (NOT an ``LlmAgent``): a numeric LSTM, not a
language model, so it cannot hallucinate a command. It runs the PREDICT stage —
forecasting near-future load with the real LSTM in the H-TRACE core — and writes
the forecast to session state for the Decision agent.
"""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from agents.regional_coordinator.edge_agents.ml_base import ml_event
from agents.regional_coordinator.edge_agents.prediction_agent.tools import (
    forecast_traffic,
)


class PredictionMLAgent(BaseAgent):
    """PREDICT stage — LSTM traffic forecaster. Deterministic, no LLM."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        tower = state.get("tower_id", "tower_1")

        fc = forecast_traffic(tower)                   # real LSTM forecast
        next_kpi = fc.get("lstm_next_kpi")
        if next_kpi is None:
            next_kpi = fc["forecasts"][0]["predicted_kpi"]
        delta = {
            "prediction_result": fc,
            "predicted_load": float(next_kpi),
            "forecast_model": fc["model"],
            "surge_risk": fc["surge_risk"],
        }
        text = (f"[Prediction · {fc['model']}] tower={tower} next_kpi={next_kpi} "
                f"surge_risk={fc['surge_risk']}")
        yield ml_event(self.name, text, delta)


prediction_agent = PredictionMLAgent(
    name="prediction_agent",
    description="Prediction Agent — non-generative LSTM traffic forecaster (PREDICT). No LLM.",
)
