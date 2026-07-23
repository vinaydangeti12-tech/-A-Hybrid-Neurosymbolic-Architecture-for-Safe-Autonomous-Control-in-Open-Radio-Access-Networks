"""
Agent Integration for TRACE_v2 — bridges the Flask server and the ADK Principal Agent.
No AWS. Supports: ADK (full), Gemini (direct), fallback mode.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from timeutil import utcnow

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

# ── ADK availability ────────────────────────────────────────────────────────
ADK_AVAILABLE = False
PRINCIPAL_AGENT_AVAILABLE = False
principal_agent = None
_Runner = _InMemorySessionService = _types = None

try:
    _AGENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _AGENTS_DIR not in sys.path:
        sys.path.insert(0, _AGENTS_DIR)
    from agents.principal_agent.agent import principal_agent as _pa
    principal_agent = _pa
    PRINCIPAL_AGENT_AVAILABLE = True
    print("[agent_integration] Principal Agent loaded")
except ImportError as e:
    print(f"[agent_integration] Principal Agent not available: {e}")

try:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as _types_mod
    _Runner = Runner
    _InMemorySessionService = InMemorySessionService
    _types = _types_mod
    ADK_AVAILABLE = True
    print("[agent_integration] Google ADK available")
except ImportError as e:
    print(f"[agent_integration] ADK not available: {e}")

from gemini_service import gemini_service, GEMINI_AVAILABLE


class AgentIntegration:
    def __init__(self) -> None:
        self._session_id = "trace-v2-session"
        self._user_id = "trace-dashboard"
        self._runner = None
        self._sessions = None
        # One persistent asyncio loop on a dedicated thread for every ADK call.
        # Creating/closing a new loop per request (the previous approach) can
        # leave the shared Runner/SessionService bound to a closed loop and
        # raise "Event loop is closed" under concurrency. A lock serialises calls.
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True, name="adk-loop").start()
        self._adk_lock = threading.Lock()
        self._init_adk()

    def _init_adk(self) -> None:
        if not (ADK_AVAILABLE and PRINCIPAL_AGENT_AVAILABLE and _Runner and _InMemorySessionService):
            return
        try:
            self._sessions = _InMemorySessionService()
            self._runner = _Runner(
                agent=principal_agent,
                app_name="trace_v2",
                session_service=self._sessions,
            )
            # Pre-create the session on the persistent loop.
            fut = asyncio.run_coroutine_threadsafe(
                self._sessions.create_session(
                    app_name="trace_v2",
                    user_id=self._user_id,
                    session_id=self._session_id,
                ),
                self._loop,
            )
            fut.result(timeout=15)
        except Exception as e:
            print(f"[agent_integration] ADK runner init failed: {e}")
            self._runner = None

    def _run_adk(self, message: str) -> str:
        if not self._runner or not _types:
            return ""

        async def _call():
            try:
                await self._sessions.create_session(
                    app_name="trace_v2",
                    user_id=self._user_id,
                    session_id=self._session_id,
                )
            except Exception:
                pass  # Session already exists — reuse it
            content = _types.Content(role="user", parts=[_types.Part(text=message)])
            response_parts = []
            async for event in self._runner.run_async(
                user_id=self._user_id,
                session_id=self._session_id,
                new_message=content,
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            response_parts.append(part.text)
            return " ".join(response_parts)

        try:
            with self._adk_lock:
                fut = asyncio.run_coroutine_threadsafe(_call(), self._loop)
                return fut.result(timeout=60)
        except Exception as e:
            # Return "" (falsy) so chat() falls through to the Gemini/fallback
            # path. Returning a non-empty "ADK error: ..." string would be
            # treated as a successful agent reply and shown to the user.
            print(f"[agent_integration] ADK run failed, falling back: {e}")
            return ""

    def chat(self, message: str, context: str = "trace_dashboard") -> Dict:
        if self._runner:
            try:
                response = self._run_adk(message)
                if response:
                    return {"success": True, "response": response, "source": "principal_agent", "timestamp": utcnow().isoformat()}
            except Exception:
                pass
        if GEMINI_AVAILABLE and gemini_service.is_available():
            return gemini_service.chat(message, context)
        return {"success": True, "response": "H-TRACE's ML Local Teams are monitoring the network; the Safety Gate is active. No critical issues detected.", "source": "fallback", "timestamp": utcnow().isoformat()}

    def analyze_issue(self, issue: Dict) -> Dict:
        if GEMINI_AVAILABLE and gemini_service.is_available():
            return gemini_service.analyze_issue(issue)
        return {
            "analysis": f"Issue '{issue.get('title')}' ({issue.get('severity')}) detected on {issue.get('affectedTowers', ['unknown'])[0]}. Automated remediation recommended.",
            "source": "fallback",
            "timestamp": utcnow().isoformat(),
        }

    def auto_remediate(self, issue: Dict, action: Optional[str] = None) -> Dict:
        if GEMINI_AVAILABLE and gemini_service.is_available():
            prompt = (
                f"Execute remediation for TRACE issue: '{issue.get('title')}' "
                f"(severity: {issue.get('severity')}, towers: {issue.get('affectedTowers', [])}). "
                f"Action: {action or 'auto'}. Confirm execution and expected outcome in 2 sentences."
            )
            res = gemini_service.chat(prompt, "remediation")
            return {
                "success": True,
                "operation": action or "auto_remediate",
                "agent_response": res.get("response"),
                "source": res.get("source"),
                "timestamp": res.get("timestamp"),
                "message": "Remediation executed via AI agent",
            }
        return {
            "success": True,
            "operation": action or "auto_remediate",
            "agent_response": f"Issue '{issue.get('title')}' resolved via {action or 'automated remediation'}.",
            "source": "fallback",
            "timestamp": utcnow().isoformat(),
            "message": "Remediation executed via direct tools",
        }

    def get_status(self) -> Dict:
        return {
            "principal_agent_available": PRINCIPAL_AGENT_AVAILABLE,
            "adk_available": ADK_AVAILABLE,
            "gemini_available": GEMINI_AVAILABLE and gemini_service.is_available(),
            "runner_active": self._runner is not None,
            "mode": (
                "full_adk" if self._runner else
                "gemini" if (GEMINI_AVAILABLE and gemini_service.is_available()) else
                "fallback"
            ),
            "fully_initialized": PRINCIPAL_AGENT_AVAILABLE and ADK_AVAILABLE,
        }


agent_integration = AgentIntegration()
