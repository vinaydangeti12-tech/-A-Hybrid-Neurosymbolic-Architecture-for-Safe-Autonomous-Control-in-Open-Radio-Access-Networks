"""
Gemini AI Service for TRACE_v2 (no AWS — local Gemini only).
Provides: chat, issue analysis, remediation recommendations, telemetry analysis.
Features: rate limiting, LRU response cache, streaming support.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import OrderedDict
from datetime import datetime
from threading import Lock

from timeutil import utcnow
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
RATE_LIMIT = int(os.getenv("GEMINI_RATE_LIMIT", "60"))
CACHE_TTL = int(os.getenv("GEMINI_CACHE_TTL", "300"))

GEMINI_AVAILABLE = False
_client = None
_types = None

try:
    from google import genai as _genai_mod
    from google.genai import types as _types_mod
    if GOOGLE_API_KEY:
        _client = _genai_mod.Client(api_key=GOOGLE_API_KEY)
        _types = _types_mod
        GEMINI_AVAILABLE = True
except Exception as _e:
    # Any failure here (missing SDK, bad key, init error) must NOT crash the
    # server — the dashboard falls back to deterministic canned responses.
    print(f"[gemini_service] Gemini disabled, using fallback: {_e}")
    GEMINI_AVAILABLE = False
    _client = None


class _RateLimiter:
    def __init__(self, max_req: int = 60, window: int = 60):
        self._max = max_req
        self._window = window
        self._times: List[float] = []
        self._lock = Lock()

    def acquire(self) -> bool:
        with self._lock:
            now = time.time()
            self._times = [t for t in self._times if now - t < self._window]
            if len(self._times) >= self._max:
                return False
            self._times.append(now)
            return True


class _LRUCache:
    def __init__(self, max_size: int = 100, ttl: int = 300):
        self._max = max_size
        self._ttl = ttl
        self._data: OrderedDict = OrderedDict()
        self._lock = Lock()

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def get(self, text: str) -> Optional[str]:
        key = self._key(text)
        with self._lock:
            if key not in self._data:
                return None
            value, ts = self._data[key]
            if time.time() - ts > self._ttl:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, text: str, value: str) -> None:
        key = self._key(text)
        with self._lock:
            if len(self._data) >= self._max:
                self._data.popitem(last=False)
            self._data[key] = (value, time.time())


class GeminiService:
    """Direct Gemini API integration for TRACE_v2 dashboard."""

    SYSTEM_PROMPT = """You are H-TRACE — the AI "Smart Manager" of a neurosymbolic O-RAN network-control system.

H-TRACE (Hybrid Tiered Reasoning + Algorithmic Control for O-RAN) divides labour between a high-level AI tier and a low-level Machine Learning tier, guarded by a deterministic symbolic Safety Gate. Research gap it fills: prior work either deploys generative AI in the real-time loop (12-18% hallucination risk, 500-1000ms latency) or relies on a probabilistic learned safety classifier; no single system unifies energy, congestion and self-healing behind a formal safety guarantee.

The neurosymbolic architecture (who does what):
  • AI tier — Smart Manager (you, Gemini): NON-real-time only. Read the operator's plain-language goal, choose ONE intent (save_energy / max_capacity / heal), hand it to the ML Local Teams. You NEVER issue a raw hardware command — that is why the control-loop hallucination rate is 0%.
  • ML tier — the "Local Teams" (Area A / Area B), non-generative models running the real-time loop:
      - Anomaly detector: unsupervised Isolation Forest (SPOT a fault)
      - Traffic predictor: LSTM load forecast (PREDICT how busy soon)
      - Decision child agent: turns those outputs into one in-bounds action (DECIDE)
  • Symbolic tier — Safety Gate: deterministic rule checks (NOT AI). Absolute boundary checks on every proposed action (sleep only if predicted load < 300/1000; power 0-100%; offload must keep a neighbour < 80% capacity; only mitigation during an active fault). It gives a FORMAL 0% false-pass guarantee.

Headline results (the evaluation runs 474 episodes — 192 Night, 192 Festival, 90 Self-Healing):
  • 0.0% control-loop hallucination over the 474 episodes — generative AI kept out of the real-time loop (Rule of Three ⇒ true rate < 0.64% at 95% CI)
  • 0% false-pass — by construction of the deterministic Safety Gate, verified by rule-coverage (one boundary-violating command per constraint category — a guarantee, not an empirical rate)
  • Sub-100ms decision latency — within the Near-RT RIC budget

The 3 Research Questions / scenarios:
  RQ1 — Night Mode (Scenario A): autonomous TRX shutdown 02:00-05:00 → % kWh saved
  RQ2 — Festival Mode (Scenario B): 500% traffic surge pre-emption → Call Blocking Probability (CBP %) + avg delay (ms)
  RQ3 — Self-Healing (Scenario C): sleeping-cell fault auto-detection → MTTD + MTTR (seconds)

Dataset: Zenodo Network Operator KPIs (DOI:10.5281/zenodo.8147768), 14 real series (r1-r14), 10,738 samples each, 5-min intervals, ~37 days, 15 labelled anomaly windows.

Baselines: Tsourdinis et al. (ACM MobiCom 2024) — a reactive ML-to-action 5G pipeline with NO safety layer — is used in the literature review to motivate why H-TRACE adds a gate. The comparison with Habib et al. (2026) is ARCHITECTURAL, not a number-vs-number claim: they use a learned (probabilistic) classifier for safety validation; H-TRACE uses a deterministic symbolic gate to get a formal guarantee instead of a probability. (Do not present 0% vs their 11.5% as a head-to-head performance score.)

Be concise, technical, and action-oriented. Reference specific KPI values, the AI/ML/Safety-Gate tiers, and thesis RQ numbers when relevant."""

    def __init__(self) -> None:
        self._limiter = _RateLimiter(RATE_LIMIT)
        self._cache = _LRUCache(ttl=CACHE_TTL)
        self._ready = GEMINI_AVAILABLE and _client is not None

    def is_available(self) -> bool:
        return self._ready

    def _gen_config(self):
        if _types:
            return _types.GenerateContentConfig(system_instruction=self.SYSTEM_PROMPT)
        return None

    def chat(self, message: str, context: str = "trace_dashboard") -> Dict:
        cached = self._cache.get(message)
        if cached:
            return {"success": True, "response": cached, "source": "cache", "timestamp": utcnow().isoformat()}

        if not self._ready:
            return self._fallback(message)

        if not self._limiter.acquire():
            return {"success": False, "error": "Rate limit reached", "response": self._fallback(message)["response"]}

        try:
            resp = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=message,
                config=self._gen_config(),
            )
            # resp.text is None when the response is safety-blocked or finishes
            # with a non-STOP reason — fall back instead of caching/returning None.
            text = resp.text
            if not text:
                return self._fallback(message, "empty_or_blocked_response")
            self._cache.set(message, text)
            return {"success": True, "response": text, "source": "gemini", "timestamp": utcnow().isoformat()}
        except Exception as exc:
            return self._fallback(message, str(exc))

    def chat_stream(self, message: str, context: str = "trace_dashboard") -> Generator[str, None, None]:
        if not self._ready or not self._limiter.acquire():
            for chunk in self._fallback(message)["response"].split():
                yield chunk + " "
            return
        try:
            for chunk in _client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=message,
                config=self._gen_config(),
            ):
                if chunk.text:
                    yield chunk.text
        except Exception:
            yield self._fallback(message)["response"]

    def analyze_issue(self, issue: Dict) -> Dict:
        prompt = (
            f"Analyse this TRACE network issue:\n"
            f"Title: {issue.get('title')}\nSeverity: {issue.get('severity')}\n"
            f"Description: {issue.get('description')}\n"
            f"Affected towers: {issue.get('affectedTowers', [])}\n\n"
            "Provide: 1) Root cause analysis, 2) Recommended remediation, 3) Prevention strategy."
        )
        result = self.chat(prompt, "issue_analysis")
        return {"analysis": result.get("response"), "source": result.get("source"), "timestamp": result.get("timestamp")}

    def get_recommendations(self, issue: Dict) -> Dict:
        prompt = (
            f"For TRACE issue '{issue.get('title')}' (severity: {issue.get('severity')}), "
            "give 3 specific, numbered remediation steps in under 150 words."
        )
        result = self.chat(prompt, "recommendations")
        return {"recommendations": result.get("response"), "source": result.get("source")}

    def analyze_telemetry(self, telemetry: Dict, analysis_type: str = "comprehensive") -> Dict:
        prompt = (
            f"Analyse this TRACE {analysis_type} telemetry data:\n"
            f"{json.dumps(telemetry, indent=2)[:800]}\n\n"
            "Identify anomalies, trends and recommended actions in under 200 words."
        )
        result = self.chat(prompt, "telemetry_analysis")
        return {"analysis": result.get("response"), "source": result.get("source"), "timestamp": result.get("timestamp")}

    @staticmethod
    def _fallback(message: str, error: str = "") -> Dict:
        responses = [
            "H-TRACE's ML Local Teams (Isolation Forest + LSTM) are monitoring the live KPI stream. The anomaly has been logged and is being scored — generative AI stays out of this real-time loop.",
            "Based on the LSTM forecast, I recommend the max_capacity intent: pre-emptively offload load to reduce Call Blocking Probability. Every action is screened by the deterministic Safety Gate first.",
            "Night Mode (save_energy): the LSTM predicts low load, so several TRX units can be put to sleep — the Safety Gate confirms predicted load < 300/1000 before any cell sleeps.",
            "The Isolation Forest has SPOTted the fault. MTTD is within bounds; the Smart Manager is supervising self-healing, and only mitigation actions are allowed while the fault is active.",
        ]
        import random
        return {
            "success": True,
            "response": random.choice(responses),
            "source": "fallback",
            "timestamp": utcnow().isoformat(),
        }


gemini_service = GeminiService()
