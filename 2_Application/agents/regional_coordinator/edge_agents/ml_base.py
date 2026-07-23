"""Shared base for the H-TRACE edge child agents — deterministic, non-generative ML.

The five edge agents (Monitoring, Prediction, Decision, Action, Learning) are
implemented as ADK *custom* ``BaseAgent`` agents, **not** ``LlmAgent``: they
contain NO language model, so they have no hallucination surface. Each runs one
stage of the real-time ML Local-Team loop —

    SPOT (Isolation Forest) -> PREDICT (LSTM) -> DECIDE (policy + Safety Gate)
    -> ACT (gate-approved only) -> LEARN

— by calling the real ML core (agents/htrace_core.py) and the deterministic
tools, and hands its result to the next stage through session state. This is
what makes the application's child agents genuinely "traditional Machine
Learning" rather than LLM wrappers.
"""
from __future__ import annotations

from typing import Optional

from google.adk.events import Event, EventActions
from google.genai import types


def ml_event(author: str, text: str, state_delta: Optional[dict] = None) -> Event:
    """Build an ADK event carrying a stage summary + a session-state update."""
    return Event(
        author=author,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        actions=EventActions(state_delta=state_delta or {}),
    )
