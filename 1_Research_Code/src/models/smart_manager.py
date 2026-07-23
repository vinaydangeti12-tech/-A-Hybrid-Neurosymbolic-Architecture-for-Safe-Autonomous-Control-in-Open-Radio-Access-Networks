"""
H-TRACE Smart Manager — the high-level (non-real-time) AI tier.

Pseudocode mapping:
    WHEN the operator types what they want:
        read the request in plain language
        work out a simple goal for each area
        send that goal down to the local teams
    KEEP WATCHING the whole network:
        IF something has broken: fix it automatically

This tier is the **Gemini-powered LLM Regional Coordinator**. Per the Gap
Analysis it is deliberately confined to **non-real-time orchestration** (reading
plain-language operator intent and choosing a high-level goal). It never issues
raw control commands to the equipment — that is the ML child agents' job, and
every action is still validated by the deterministic Safety Gate.

Two ways to read the operator's request:
  1. **Gemini** (``gemini_client.GeminiIntentClassifier``) — real language
     understanding, used when an API key is configured.
  2. **Keyword mapper** (deterministic, offline) — the automatic fallback when
     no key is set or the network call fails. This keeps every experiment fully
     reproducible and runnable with no internet.

Because Gemini is only ever choosing a *high-level goal* (never a command), a
wrong LLM answer cannot produce an unsafe action: the ML loop + Safety Gate sit
between this tier and the equipment. That separation is what lets H-TRACE use an
LLM for the human-facing part while keeping a 0% control-loop hallucination rate.
"""
from __future__ import annotations

from typing import Optional

from .. import config as C
from .child_agent import (INTENT_HEAL, INTENT_MAX_CAPACITY, INTENT_SAVE_ENERGY)
from ..gemini_client import GeminiIntentClassifier, IntentResult

# Keyword -> intent mapping (the deterministic fallback / baseline classifier).
_INTENT_KEYWORDS = {
    INTENT_SAVE_ENERGY: ("save energy", "energy", "power saving", "night",
                         "reduce power", "low traffic", "sleep"),
    INTENT_MAX_CAPACITY: ("capacity", "festival", "peak", "max throughput",
                          "handle load", "busy", "scale up", "high traffic"),
    INTENT_HEAL: ("heal", "fault", "fix", "restore", "outage", "incident",
                  "self-healing", "recover"),
}


def _gemini_wanted() -> bool:
    """Decide whether to try Gemini, based on config.GEMINI_ENABLED.

    "auto" (default) -> use Gemini if a key is available; otherwise keyword.
    "1"              -> force-try Gemini.
    "0"              -> never use Gemini (pure-offline keyword mode).
    """
    flag = str(C.GEMINI_ENABLED).lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return True   # "auto" and "1" both attempt Gemini (which itself no-ops w/o a key)


class SmartManager:
    """Translates operator intent to per-area goals and supervises healing.

    Parameters
    ----------
    use_gemini : Optional[bool]
        ``None`` (default) follows ``config.GEMINI_ENABLED``. ``True``/``False``
        force the behaviour (handy for the intent-evaluation experiment, which
        compares the keyword baseline against Gemini head-to-head).
    classifier : Optional[GeminiIntentClassifier]
        Inject a shared classifier (so we build the client only once across many
        requests). If omitted, one is created lazily on first use.
    """

    def __init__(self, use_gemini: Optional[bool] = None,
                 classifier: Optional[GeminiIntentClassifier] = None):
        self.warnings: list[str] = []          # audit trail of blocked actions
        self.intent_log: list[IntentResult] = []  # audit trail of intent decisions
        self._use_gemini = _gemini_wanted() if use_gemini is None else use_gemini
        self._classifier = classifier
        self._classifier_built = classifier is not None

    # -- lazy classifier so importing this module never hits the network --- #
    def _get_classifier(self) -> Optional[GeminiIntentClassifier]:
        if not self._use_gemini:
            return None
        if not self._classifier_built:
            self._classifier = GeminiIntentClassifier()
            self._classifier_built = True
        return self._classifier

    @property
    def gemini_active(self) -> bool:
        clf = self._get_classifier()
        return bool(clf and clf.available)

    # -- the deterministic fallback (also used as a research baseline) ------ #
    def parse_intent_keyword(self, operator_request: str) -> IntentResult:
        text = operator_request.lower()
        scores = {intent: sum(kw in text for kw in kws)
                  for intent, kws in _INTENT_KEYWORDS.items()}
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            best = INTENT_HEAL                  # safe default when nothing matches
        total = sum(scores.values())
        conf = (scores[best] / total) if total else 0.0
        return IntentResult(intent=best, confidence=conf,
                            reasoning=f"keyword matches={scores}",
                            source="keyword-fallback")

    # -- "read the request in plain language" ----------------------------- #
    def classify(self, operator_request: str) -> IntentResult:
        """Full intent decision: try Gemini first, fall back to keywords.

        Always returns a valid IntentResult and records it in ``intent_log``.
        """
        clf = self._get_classifier()
        if clf is not None and clf.available:
            result = clf.classify(operator_request)
            if result is not None:
                self.intent_log.append(result)
                return result
        # Fallback path (no key, network error, or invalid model output).
        result = self.parse_intent_keyword(operator_request)
        self.intent_log.append(result)
        return result

    def parse_intent(self, operator_request: str) -> str:
        """Backwards-compatible helper: return just the intent string."""
        return self.classify(operator_request).intent

    # -- "work out a simple goal for each area" --------------------------- #
    def assign_goals(self, operator_request: str, areas) -> dict:
        intent = self.parse_intent(operator_request)
        return {area: intent for area in areas}

    # -- "IF something has broken: fix it / warn" ------------------------- #
    def on_gate_decision(self, area: str, decision) -> None:
        if decision.blocked:
            self.warnings.append(
                f"[{area}] BLOCKED {decision.action.type.value} "
                f"cell={decision.action.cell_id} reasons={decision.reasons}")


if __name__ == "__main__":
    mgr = SmartManager()
    print("Smart Manager intent tier:",
          "Gemini" if mgr.gemini_active else "keyword fallback")
    for req in ["Please save energy on the quiet night cells",
                "We expect a festival, handle the peak capacity",
                "There is an outage, restore service",
                "do whatever"]:
        r = mgr.classify(req)
        print(f"{req!r:55} -> {r.intent:<12} "
              f"(conf={r.confidence:.2f}, via {r.source})")
