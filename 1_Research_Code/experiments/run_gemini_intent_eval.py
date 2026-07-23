"""
H-TRACE — research experiment: Gemini vs keyword intent translation.

RESEARCH QUESTION
-----------------
Does using Gemini in the Smart Manager actually improve how well H-TRACE
understands a human operator's plain-language request, compared with the simple
deterministic keyword mapper it falls back to?

This is the *measurable* contribution of the AI tier. It is deliberately
separate from the safety results: the Safety Gate's 0% false-pass guarantee does
NOT depend on which intent classifier is used — that is the whole point of the
neurosymbolic split. Here we only measure language understanding.

METHOD
------
We hand-label a set of realistic operator commands with their correct intent
(save_energy / max_capacity / heal). Many are written *indirectly* — the way a
real engineer would type them ("the stadium is sold out tonight") — so they do
NOT contain the obvious keywords. We then measure classification accuracy for:

  * Keyword baseline  (deterministic, offline)
  * Gemini            (the LLM Smart Manager)

OUTPUT
------
  results/tables/gemini_intent_eval.csv   per-command predictions
  results/tables/gemini_intent_summary.csv accuracy summary
  results/figures/fig_gemini_intent_accuracy.png

Run:
    python -m experiments.run_gemini_intent_eval

If no GEMINI_API_KEY is configured, only the keyword baseline is scored and the
script tells you how to enable Gemini.
"""
from __future__ import annotations

import sys
import warnings

warnings.filterwarnings("ignore")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import config as C
from src.gemini_client import GeminiIntentClassifier
from src.models.smart_manager import SmartManager


# --------------------------------------------------------------------------- #
# Hand-labelled operator commands (ground truth).
# "easy" commands contain obvious keywords; "hard" commands are phrased
# indirectly — these are where an LLM should beat keyword matching.
# --------------------------------------------------------------------------- #
LABELLED_COMMANDS = [
    # ---- save_energy ---------------------------------------------------- #
    ("Please save energy on the quiet night cells.", "save_energy", "easy"),
    ("Traffic is low overnight, reduce power consumption.", "save_energy", "easy"),
    ("Put the idle sectors to sleep until morning.", "save_energy", "easy"),
    ("It's 3am and barely anyone is connected — trim the power.", "save_energy", "hard"),
    ("Nobody's around, let's cut the electricity bill on those towers.", "save_energy", "hard"),
    ("Switch off whatever we don't need right now to go green.", "save_energy", "hard"),
    ("Dial things down for the night shift.", "save_energy", "hard"),
    ("We want to be more sustainable when demand is minimal.", "save_energy", "hard"),
    # ---- max_capacity --------------------------------------------------- #
    ("Festival tonight, handle the peak capacity.", "max_capacity", "easy"),
    ("Scale up, we expect very high traffic.", "max_capacity", "easy"),
    ("Keep all cells awake to handle the busy period.", "max_capacity", "easy"),
    ("The stadium is sold out tonight — don't let anything drop.", "max_capacity", "hard"),
    ("Huge crowd expected downtown, make sure everyone gets service.", "max_capacity", "hard"),
    ("New Year's Eve is going to hammer the network, be ready.", "max_capacity", "hard"),
    ("Concert just let out and everyone's posting videos at once.", "max_capacity", "hard"),
    ("Give me maximum throughput, the area is slammed.", "max_capacity", "hard"),
    # ---- heal ----------------------------------------------------------- #
    ("There is an outage, restore service.", "heal", "easy"),
    ("A cell has faulted, please self-heal it.", "heal", "easy"),
    ("Fix the incident on the network now.", "heal", "easy"),
    ("Customers in sector 3 are getting dropped calls.", "heal", "hard"),
    ("Something's gone dark on the east side, bring it back.", "heal", "hard"),
    ("Users report no signal near the highway tower.", "heal", "hard"),
    ("That base station crashed again, get it running.", "heal", "hard"),
    ("Service is down for a whole neighbourhood, sort it out.", "heal", "hard"),
]


def evaluate(predict_fn, name: str) -> pd.DataFrame:
    """Run a classifier (a function text->intent) over every labelled command."""
    rows = []
    for text, gold, difficulty in LABELLED_COMMANDS:
        try:
            pred = predict_fn(text)
        except Exception:
            pred = "ERROR"
        rows.append({
            "classifier": name,
            "command": text,
            "difficulty": difficulty,
            "gold": gold,
            "pred": pred,
            "correct": int(pred == gold),
        })
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """Accuracy overall and split by easy/hard phrasing."""
    out = []
    for name, g in df.groupby("classifier"):
        out.append({
            "classifier": name,
            "n": len(g),
            "accuracy_%": round(100 * g["correct"].mean(), 1),
            "easy_acc_%": round(100 * g[g.difficulty == "easy"]["correct"].mean(), 1),
            "hard_acc_%": round(100 * g[g.difficulty == "hard"]["correct"].mean(), 1),
        })
    return pd.DataFrame(out)


def main() -> None:
    print("=" * 74)
    print("H-TRACE — Gemini vs keyword intent-translation accuracy")
    print("=" * 74)
    print(f"Labelled operator commands: {len(LABELLED_COMMANDS)} "
          f"(intents: {', '.join(C.GEMINI_INTENTS)})\n")

    # Keyword baseline always runs (offline, deterministic).
    keyword_mgr = SmartManager(use_gemini=False)
    frames = [evaluate(lambda t: keyword_mgr.parse_intent_keyword(t).intent,
                       "Keyword baseline")]

    # Gemini, if a key is configured.
    clf = GeminiIntentClassifier()
    print(clf.status())
    if clf.available:
        gemini_mgr = SmartManager(use_gemini=True, classifier=clf)
        print("Querying Gemini for each command (one API call each)…")
        frames.append(evaluate(lambda t: gemini_mgr.classify(t).intent, "Gemini"))
    else:
        print("Skipping the Gemini column. To enable it, set your key:")
        print('  PowerShell:  $env:GEMINI_API_KEY="<your key>"')
        print("  then re-run: python -m experiments.run_gemini_intent_eval")

    details = pd.concat(frames, ignore_index=True)
    summary = summarise(details)

    # --- persist ---------------------------------------------------------- #
    C.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    details.to_csv(C.TABLES_DIR / "gemini_intent_eval.csv", index=False)
    summary.to_csv(C.TABLES_DIR / "gemini_intent_summary.csv", index=False)

    # --- figure ----------------------------------------------------------- #
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(summary))
    width = 0.38
    ax.bar([i - width/2 for i in x], summary["easy_acc_%"], width,
           label="Easy (keyword-friendly)", color="#9ecae1")
    ax.bar([i + width/2 for i in x], summary["hard_acc_%"], width,
           label="Hard (indirect phrasing)", color="#3182bd")
    for i, row in summary.iterrows():
        ax.text(i, row["accuracy_%"] + 1, f"{row['accuracy_%']:.0f}% overall",
                ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(summary["classifier"])
    ax.set_ylabel("intent accuracy (%)")
    ax.set_ylim(0, 109)
    ax.set_title("Operator-intent translation: Gemini vs keyword baseline\n"
                 "(the Safety Gate's 0% false-pass guarantee is unaffected either way)",
                 fontsize=10, fontweight="bold")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(C.FIGURES_DIR / "fig_gemini_intent_accuracy.png", dpi=120)
    plt.close(fig)

    # --- report ----------------------------------------------------------- #
    print("\n" + "-" * 74)
    print("SUMMARY (accuracy by classifier)")
    print("-" * 74)
    print(summary.to_string(index=False))
    print("\nWhere they differ (hard / indirect commands):")
    hard = details[details.difficulty == "hard"]
    pivot = hard.pivot_table(index="command", columns="classifier",
                             values="pred", aggfunc="first")
    gold_map = {t: g for t, g, _ in LABELLED_COMMANDS}
    pivot.insert(0, "gold", [gold_map[c] for c in pivot.index])
    with pd.option_context("display.max_colwidth", 52, "display.width", 200):
        print(pivot.to_string())

    print(f"\nTables  -> {C.TABLES_DIR}")
    print(f"Figure  -> {C.FIGURES_DIR / 'fig_gemini_intent_accuracy.png'}")
    if not clf.available:
        print("\n(Only the keyword baseline was scored — enable Gemini to compare.)")


if __name__ == "__main__":
    main()
