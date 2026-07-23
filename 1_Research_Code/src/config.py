"""
H-TRACE — Global configuration.

H-TRACE: Hybrid Tiered Reasoning + Algorithmic Control for O-RAN.

A hybrid neurosymbolic architecture that divides labour between a high-level
(non-real-time) AI Smart Manager and low-level, *non-generative* Machine
Learning child agents ("Local Teams"), with a deterministic, rule-based
Safety Gate guarding every action before it reaches the network equipment.

This module centralises every path, hyper-parameter, scenario definition and
safety bound so the whole experiment is reproducible from one place.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = PROJECT_ROOT / "data" / "raw" / "extracted" / "network_operator_KPIs_time_series_dataset"
# Fall back to the dataset bundled with this submission (../3_Dataset) when the
# default extracted location is absent, so the research code runs standalone.
if not DATA_RAW.is_dir():
    _bundled = PROJECT_ROOT.parent / "3_Dataset" / "network_operator_KPIs_time_series_dataset"
    if _bundled.is_dir():
        DATA_RAW = _bundled
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_DIR = RESULTS_DIR / "tables"

for _d in (DATA_PROCESSED, RESULTS_DIR, FIGURES_DIR, TABLES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

REAL_DIR = DATA_RAW / "data_real"
SERIES_DIR = DATA_RAW / "data_series"
INCIDENTS_FILE = DATA_RAW / "data_real_incidents.txt"
REAL_INFO_FILE = DATA_RAW / "data_real_info.txt"
SERIES_INFO_FILE = DATA_RAW / "data_series_info.txt"

# --------------------------------------------------------------------------- #
# Dataset constants
# --------------------------------------------------------------------------- #
SAMPLE_PERIOD_SEC = 300          # 5-minute KPI sampling interval
SAMPLES_PER_DAY = 24 * 60 // 5   # 288 samples per day
VALUE_SCALE = 1000.0             # KPIs are normalised to [0, 1000] per series
KPI_TYPES = ("internet", "sessions", "vpn", "downstream")

# --------------------------------------------------------------------------- #
# Reproducibility
# --------------------------------------------------------------------------- #
RANDOM_SEED = 42

# --------------------------------------------------------------------------- #
# Gemini Smart Manager (the high-level, NON-real-time AI tier)
# --------------------------------------------------------------------------- #
# Gemini is used ONLY by the Smart Manager to translate a human operator's
# plain-language request into one of the three structured intents below. It is
# deliberately kept OUT of the real-time control loop (that stays pure ML +
# the deterministic Safety Gate), so generative AI can never issue a raw
# command to the equipment — this is what keeps the control-loop hallucination
# rate at 0%. If no API key is configured, the Smart Manager automatically
# falls back to a deterministic keyword mapper, so every experiment still runs
# fully offline and reproducibly.
#
# The API key is read from the GEMINI_API_KEY environment variable (or a .env
# file). NEVER hard-code your key in source. See .env.example.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Turn the Gemini tier on/off globally. Default: use it only if a key is set.
GEMINI_ENABLED = os.environ.get("GEMINI_ENABLED", "auto")   # "auto" | "1" | "0"
GEMINI_TIMEOUT_S = 20          # network timeout for a single intent call
# The three operator intents Gemini must choose between (must match child_agent).
GEMINI_INTENTS = ("save_energy", "max_capacity", "heal")

# --------------------------------------------------------------------------- #
# Multi-agent hierarchy — two parallel "Local Teams" (Area A / Area B)
# Each KPI stream (a "cell") is assigned to exactly one area team.
# --------------------------------------------------------------------------- #
AREAS = ("Area_A", "Area_B")

# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
INTERP_LIMIT = SAMPLES_PER_DAY   # max consecutive gap (samples) to interpolate
ROLLING_WINDOW = 12              # 1 hour of context for rolling features

# --------------------------------------------------------------------------- #
# Anomaly detector (Isolation Forest) — H-TRACE "SPOT a fault"
# --------------------------------------------------------------------------- #
IFOREST_PARAMS = dict(
    n_estimators=200,
    contamination=0.02,          # ~2% of points flagged; tuned to fault rarity
    max_samples="auto",
    random_state=RANDOM_SEED,
    n_jobs=-1,
)

# --------------------------------------------------------------------------- #
# Traffic predictor (LSTM) — H-TRACE "PREDICT how busy soon"
# --------------------------------------------------------------------------- #
LSTM_PARAMS = dict(
    input_window=24,             # use last 24 samples (2 h of context) ...
    horizon=12,                  # ... to predict load 1 h ahead (proactive).
    # Rationale: H-TRACE needs to know how busy a cell will get *soon* so it can
    # act before congestion. At 1-step-ahead, naive persistence is near-optimal
    # on this smooth data; at a 1 h operational horizon the LSTM's learned daily
    # seasonality gives a clear edge on high-variability traffic.
    hidden_size=48,
    num_layers=1,
    dropout=0.0,
    lr=1e-3,
    epochs=25,
    batch_size=128,
    train_frac=0.8,              # chronological train/test split per series
)

# --------------------------------------------------------------------------- #
# Safety Gate — deterministic, rule-based boundary checks (NOT AI)
# Hard physical/operational limits the network must never violate.
# Values are on the dataset's 0–1000 KPI scale (load %  ==  value / 10).
# --------------------------------------------------------------------------- #
SAFETY_BOUNDS = dict(
    # A cell may only be switched OFF for energy saving when predicted load is
    # genuinely low; switching off a busy cell would cause an outage.
    sleep_max_predicted_load=300.0,      # never sleep a cell if pred load > 300 (30%)
    # Power / capacity scaling must stay within hardware limits.
    power_min_pct=0.0,
    power_max_pct=100.0,
    # Traffic offloaded to a neighbour cell must not exceed its headroom.
    neighbor_capacity=1000.0,
    max_offload_fraction=0.8,            # never push a neighbour above 80% capacity
    # Predicted-load sanity: an action premised on an impossible load is unsafe.
    load_min=0.0,
    load_max=1000.0,
    # During an *active, confirmed fault* the only permitted actions are
    # mitigation (reroute / restart); optimisation actions are blocked.
    block_optimisation_during_fault=True,
)

# --------------------------------------------------------------------------- #
# Scenario definitions  (Night / Festival / Self-Healing)
# --------------------------------------------------------------------------- #
# Night Mode    : low-traffic regime -> energy-saving (sleep) decisions dominate.
# Festival Mode : high-traffic regime -> scale-up / keep-awake decisions.
# Self-Healing  : labelled real fault windows -> detect + mitigate.
SCENARIOS = ("night", "festival", "self_healing")

# Quantile thresholds (per series) used to carve low / high traffic regimes.
NIGHT_QUANTILE = 0.33            # samples below the 33rd percentile = "night"
FESTIVAL_QUANTILE = 0.90         # samples above the 90th percentile = "festival/peak"

EPISODE_WINDOW = 24              # 2 hours of samples per episode

# --------------------------------------------------------------------------- #
# Experiment protocol
# --------------------------------------------------------------------------- #
# Total episodes across all three scenarios (professor-confirmed protocol).
N_EPISODES = 500
EPISODE_SPLIT = {"night": 200, "festival": 200, "self_healing": 100}
# Deliberately boundary-violating commands injected to stress the Safety Gate.
N_ADVERSARIAL_COMMANDS = 50

# Rule of Three: 0 failures in N trials => true rate < 3/N at 95% CI.
def rule_of_three_upper_bound(n_trials: int) -> float:
    """Upper 95% CI bound on the true failure rate given 0 observed failures."""
    return 3.0 / n_trials if n_trials > 0 else float("nan")

# Sample mode — keep evaluation runs fast. Set HTRACE_FULL=1 to use every series.
USE_SAMPLE = os.environ.get("HTRACE_FULL", "0") != "1"
SAMPLE_N_SYNTHETIC = 16          # synthetic series used in sample mode (of 48)
