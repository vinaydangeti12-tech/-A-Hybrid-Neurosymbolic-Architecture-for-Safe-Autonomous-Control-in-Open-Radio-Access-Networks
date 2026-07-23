"""
H-TRACE — Gemini client for the Smart Manager (the high-level AI tier).

WHAT THIS DOES (in one sentence)
--------------------------------
It asks Google's Gemini model to read a network operator's plain-English request
(e.g. "the stadium is packed tonight, keep the cells up") and return ONE of three
machine-usable intents: ``save_energy``, ``max_capacity`` or ``heal``.

WHY GEMINI LIVES HERE AND NOWHERE ELSE (important for the thesis)
----------------------------------------------------------------
H-TRACE is a *neurosymbolic* design. Generative AI (Gemini) is allowed only in
the **non-real-time** Smart Manager, where it does language understanding. It
NEVER touches the real-time control loop — that stays pure, non-generative ML
(Isolation Forest + LSTM) plus a deterministic Safety Gate. So even if Gemini
ever returns a wrong or "hallucinated" answer, the worst that can happen is the
wrong *high-level goal*; every concrete action is still produced by ML and then
checked by the Safety Gate before it can reach the equipment. This is exactly
why H-TRACE can claim a 0% control-loop hallucination rate while still using an
LLM for the human-facing part.

SAFE KEY HANDLING
-----------------
The API key is read from the ``GEMINI_API_KEY`` environment variable (or a
local ``.env`` file). It is never written into source code. If no key is found,
``GeminiIntentClassifier.available`` is ``False`` and the Smart Manager simply
falls back to a deterministic keyword mapper, so the whole project still runs
offline.

DESIGN GOAL: SIMPLICITY
-----------------------
This file has no clever tricks. One class, a couple of small methods, lots of
comments. Anyone should be able to read it top to bottom and understand it.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from . import config as C

# Load variables from a local .env file if python-dotenv is installed.
# (Optional dependency — the code works fine without it as long as the
#  environment variable is set some other way.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# --------------------------------------------------------------------------- #
# The structured result Gemini gives us back.
# --------------------------------------------------------------------------- #
@dataclass
class IntentResult:
    """A single, fully-audited intent decision."""
    intent: str                 # one of config.GEMINI_INTENTS
    confidence: float           # 0..1, how sure the model is
    reasoning: str              # one short human-readable sentence (audit trail)
    source: str                 # "gemini" or "keyword-fallback"
    raw: str = ""               # the raw model text (kept for the audit log)


# The instruction we give Gemini. Kept deliberately strict so the answer is
# always one of our three known intents and always valid JSON.
_SYSTEM_PROMPT = """You are the Smart Manager of an autonomous 5G / O-RAN network controller.
A human network operator will type a request in plain language.
Your ONLY job is to classify that request into exactly ONE of these three intents:

- "save_energy"  : the operator wants to reduce power / save energy / put quiet
                   cells to sleep (e.g. low-traffic nights).
- "max_capacity" : the operator wants maximum capacity / to handle a traffic peak
                   or busy period (e.g. a festival or stadium event).
- "heal"         : the operator is reporting a fault / outage / incident and wants
                   the network restored or self-healed.

Rules:
- You do NOT issue any network commands. You only choose the intent.
- If the request is ambiguous or unrelated, choose the safest intent: "heal".
- Reply with ONLY a JSON object, no extra text, in this exact shape:
  {"intent": "<one of save_energy|max_capacity|heal>",
   "confidence": <number between 0 and 1>,
   "reasoning": "<one short sentence>"}"""


class GeminiIntentClassifier:
    """Thin, safe wrapper around the google-genai SDK for intent classification.

    Typical use::

        clf = GeminiIntentClassifier()
        if clf.available:
            result = clf.classify("festival tonight, keep capacity high")
            print(result.intent, result.confidence)
    """

    def __init__(self, model: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.model = model or C.GEMINI_MODEL
        # Accept the standard env var names used by Google's tools.
        self._api_key = (api_key
                         or os.environ.get("GEMINI_API_KEY")
                         or os.environ.get("GOOGLE_API_KEY"))
        self._client = None
        self._init_error: Optional[str] = None
        if self._api_key:
            self._try_init_client()

    # -- setup ------------------------------------------------------------- #
    def _try_init_client(self) -> None:
        """Create the Gemini client once. Failures are stored, never raised."""
        try:
            from google import genai            # the google-genai SDK
            self._client = genai.Client(api_key=self._api_key)
        except Exception as exc:                 # missing SDK, bad key format, ...
            self._client = None
            self._init_error = f"{type(exc).__name__}: {exc}"

    @property
    def available(self) -> bool:
        """True only if we have a key AND the client built successfully."""
        return self._client is not None

    def status(self) -> str:
        """Human-readable one-liner for logs / the demo banner."""
        if self.available:
            return f"Gemini ENABLED (model={self.model})"
        if not self._api_key:
            return ("Gemini DISABLED — no GEMINI_API_KEY found "
                    "(falling back to keyword mapper)")
        return f"Gemini DISABLED — client init failed ({self._init_error})"

    # -- the one useful method --------------------------------------------- #
    def classify(self, operator_request: str) -> Optional[IntentResult]:
        """Return an IntentResult, or None if the call could not be completed.

        Returning None (instead of raising) lets the Smart Manager fall back to
        its deterministic keyword mapper without any try/except at the call
        site — keeping the higher-level code clean.
        """
        if not self.available:
            return None

        from google.genai import types
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=operator_request,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    # Ask the API to return strict JSON — far more reliable than
                    # parsing free-form text.
                    response_mime_type="application/json",
                    # Low temperature => deterministic, repeatable classification.
                    temperature=0.0,
                    max_output_tokens=200,
                ),
            )
            text = (response.text or "").strip()
            return self._parse(text)
        except Exception:
            # Any network / quota / parsing problem -> signal "fall back".
            return None

    # -- parsing + validation ---------------------------------------------- #
    def _parse(self, text: str) -> Optional[IntentResult]:
        """Turn the model's JSON text into a validated IntentResult."""
        try:
            data = json.loads(text)
        except Exception:
            # Sometimes a model wraps JSON in ```json ... ``` fences — strip them.
            cleaned = text.strip().strip("`")
            cleaned = cleaned[cleaned.find("{"): cleaned.rfind("}") + 1]
            try:
                data = json.loads(cleaned)
            except Exception:
                return None

        intent = str(data.get("intent", "")).strip().lower()
        if intent not in C.GEMINI_INTENTS:        # guard against any odd output
            return None
        try:
            confidence = float(data.get("confidence", 0.0))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        reasoning = str(data.get("reasoning", "")).strip()[:200]
        return IntentResult(intent=intent, confidence=confidence,
                            reasoning=reasoning, source="gemini", raw=text)


# A small manual check you can run on its own:
#   python -m src.gemini_client "the stadium is packed, keep capacity high"
if __name__ == "__main__":
    import sys

    clf = GeminiIntentClassifier()
    print(clf.status())
    request = " ".join(sys.argv[1:]) or "save power on the quiet night cells"
    print(f"\nOperator says: {request!r}")
    res = clf.classify(request)
    if res is None:
        print("-> (no Gemini result; the Smart Manager would use the keyword fallback)")
    else:
        print(f"-> intent={res.intent}  confidence={res.confidence:.2f}")
        print(f"   reasoning: {res.reasoning}")
