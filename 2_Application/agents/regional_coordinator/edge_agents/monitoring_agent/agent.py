"""Monitoring Agent — non-generative ML child agent (Isolation Forest).

This is a deterministic ADK ``BaseAgent`` (NOT an ``LlmAgent``): it has no
language model and therefore cannot hallucinate. It runs the SPOT stage of the
real-time loop by scoring the live KPI with the real Isolation Forest in the
H-TRACE core, and writes the result to session state for the rest of the Local
Team.
"""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from agents.regional_coordinator.edge_agents.ml_base import ml_event
from agents.regional_coordinator.edge_agents.monitoring_agent.tools import (
    detect_anomaly,
)


class MonitoringMLAgent(BaseAgent):
    """SPOT stage — unsupervised Isolation Forest. Deterministic, no LLM."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        tower = state.get("tower_id", "tower_1")
        kpi = float(state.get("kpi_value", state.get("raw_kpi_value", 500.0)))

        result = detect_anomaly(tower, kpi)            # real Isolation Forest score
        delta = {
            "monitoring_result": result,
            "anomaly_score": result["anomaly_score"],
            "is_anomaly": result["is_anomaly"],
            "fault_active": result["is_anomaly"],
            "kpi_value": kpi,
        }
        text = (f"[Monitoring · {result['detector']}] tower={tower} kpi={kpi:.1f} "
                f"score={result['anomaly_score']} severity={result['severity']}")
        yield ml_event(self.name, text, delta)


monitoring_agent = MonitoringMLAgent(
    name="monitoring_agent",
    description="Monitoring Agent — non-generative Isolation Forest fault detector (SPOT). No LLM.",
)
