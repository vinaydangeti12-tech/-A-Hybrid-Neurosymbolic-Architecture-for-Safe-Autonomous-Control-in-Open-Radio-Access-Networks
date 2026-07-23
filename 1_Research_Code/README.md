# H-TRACE — EDA, Models, Baselines & Experimental Results

**H-TRACE** (Hybrid Tiered Reasoning + Algorithmic Control for O-RAN) is a hybrid
*neurosymbolic* architecture for autonomous O-RAN / 5G network control. It splits
the work between:

| Tier | Role | Implementation |
|------|------|----------------|
| **Smart Manager** (AI) | Non-real-time orchestration: translate operator intent → per-area goals, supervise self-healing | `src/models/smart_manager.py` + `src/gemini_client.py` — **Gemini-powered** LLM Regional Coordinator, with an automatic deterministic keyword fallback when no API key is set |
| **Local Teams** (ML child agents, Area A / Area B) | Real-time control loop: **SPOT** faults, **PREDICT** load, **DECIDE** an action | `src/models/anomaly_detector.py` (Isolation Forest), `traffic_predictor.py` (LSTM), `child_agent.py` |
| **Safety Gate** (rules, NOT AI) | Deterministic boundary checks over every proposed action before execution | `src/models/safety_gate.py` |
| **Equipment** | Cell towers / antennas; streams KPI telemetry back | simulated KPI replay |

The design eliminates **AI hallucinations** by keeping generative AI out of the
real-time loop (non-generative ML only → 0% control-loop hallucination) and
guarantees a **0% false-pass rate** via the deterministic Safety Gate.

---

## Dataset

**Network Operator KPIs Time Series Dataset** — Zenodo DOI `10.5281/zenodo.8147768`
(auto-downloaded to `data/raw/`). 14 real KPI series (with 15 labelled fault
windows) + 48 synthetic series, 5-minute sampling over ~37 days, values scaled
to `[0, 1000]`. KPI types: internet, sessions, vpn, downstream.

Scenario mapping:
- **Night Mode** — low-traffic regime of synthetic series (energy-saving intent)
- **Festival Mode** — high-traffic / peak regime (max-capacity intent)
- **Self-Healing** — labelled real fault windows (heal intent)

---

## How to run

```bash
pip install -r requirements.txt

# 1) EDA + preprocessing figures/tables
python -m src.eda
```

**Models + baselines + experimental results** are in the notebook
`experiments/run_evaluation.ipynb` — open it and **Run All** (it runs in fast
sample mode by default; set `HTRACE_FULL=1` before launching Jupyter to use every
series, slower ~7 min).

Outputs land in `results/figures/` and `results/tables/`
(`master_comparison.csv` + `evaluation_results.md` are the headline deliverables).

---

## Gemini Smart Manager (the AI tier)

The Smart Manager uses **Google Gemini** to read a network operator's
plain-language request and turn it into one of three structured intents
(`save_energy` / `max_capacity` / `heal`). Gemini is used **only** in this
non-real-time tier — it never issues a control command. Every concrete action is
produced by the ML child agents and then screened by the deterministic Safety
Gate, so the control-loop hallucination rate stays 0% even though an LLM is in
the loop for language understanding. **If no API key is configured, the Smart
Manager automatically falls back to a deterministic keyword mapper**, so the
whole project still runs fully offline.

### 1. Set your API key (never hard-code it)

Get a free key at <https://aistudio.google.com/apikey>, then either:

```powershell
# Option A — copy the template and paste your key into .env
copy .env.example .env        # then edit .env

# Option B — set it for the current PowerShell session only
$env:GEMINI_API_KEY="your_key_here"
```

`.env` is git-ignored on purpose. The key is read from the `GEMINI_API_KEY`
environment variable; it never appears in the source code.

### 2. Run the demo (plain English → AI → ML → Safety Gate)

Open the notebook `experiments/gemini_demo.ipynb` and **Run All** — it walks one
operator request through the full neurosymbolic pipeline and then shows the
Safety Gate blocking deliberately unsafe actions.

### 3. Run the research experiment (Gemini vs keyword baseline)

```bash
python -m experiments.run_gemini_intent_eval
```

This measures intent-translation accuracy on hand-labelled operator commands.
Typical result: **Gemini ≈ 100%** vs **keyword baseline ≈ 62%** — the baseline
matches only obvious keywords and collapses on indirect phrasing ("the stadium
is sold out tonight"), while Gemini understands intent. Outputs:
`results/tables/gemini_intent_summary.csv` and
`results/figures/fig_gemini_intent_accuracy.png`.

> **Thesis framing:** the LLM improves the *human-facing* intent layer; the
> Safety Gate's 0% false-pass guarantee is deterministic and does **not** depend
> on which intent classifier is used. That separation is the neurosymbolic
> contribution.

---

## Project layout

```
src/
  config.py                 global paths, hyper-params, safety bounds, Gemini config
  data_loader.py            load KPI series, labels, area assignment
  preprocessing.py          grid/gap-fill, time + rolling features, LSTM windows
  eda.py                    summary stats + figures
  gemini_client.py          Gemini wrapper for intent classification (safe key handling)
  models/
    anomaly_detector.py     Isolation Forest fault detector (H-TRACE)
    traffic_predictor.py    LSTM traffic forecaster (H-TRACE)
    safety_gate.py          deterministic rule-based Safety Gate
    child_agent.py          Local Team: detect → predict → decide
    smart_manager.py        Gemini intent translation (+ keyword fallback)
  baselines/
    detectors.py            Threshold (z-score), One-Class SVM
    forecasters.py          Persistence, Seasonal-Naive
  htrace_system.py          System wrappers (H-TRACE, ablation, baselines)
  evaluation/
    metrics.py              detection / forecast / safety / latency metrics
    scenarios.py            episode builder + Safety-Gate stress test
experiments/
  run_evaluation.ipynb      end-to-end evaluation notebook (ML + baselines + results)
  gemini_demo.ipynb         plain English → Gemini → ML → Safety Gate walkthrough
  run_gemini_intent_eval.py Gemini vs keyword intent-accuracy experiment
.env.example                template for your GEMINI_API_KEY (copy to .env)
results/figures, results/tables
```

---

## Evaluation metrics (all reported in `master_comparison.csv`)

- **Detection:** Precision, Recall, F1, ROC-AUC, PR-AUC (on labelled real faults)
- **Forecast:** MAE, RMSE, MAPE, sMAPE, R² (overall + per-KPI-type breakdown)
- **Safety:** False-Pass %, False-Block %, Control-loop Hallucination %
- **Operations:** mean / p95 decision latency (ms), % meeting the 100 ms Near-RT
  RIC budget
- **Self-healing:** fault recall over Self-Healing episodes
- **Certification:** Rule of Three 95% upper bound on the zero-defect claims

---

## Latency reproducibility

Decision latency is a **wall-clock measurement on a physical CPU**, not a quantity
computed from the fixed random seed — so, unlike every other metric, it varies
between runs (background load, power mode, thermal state). Every *deterministic*
metric (detection, forecasting, safety) is bit-for-bit identical across runs; only
latency moves. The edge loop was therefore timed three independent times:

| Run | Edge mean (ms) | Edge p95 (ms) | Episodes within 100 ms budget |
|---|---|---|---|
| 1 (initial) | 28.8 | 34.3 | 100% (474/474) |
| 2 (submitted results) | 43.0 | 56.1 | 100% (474/474) |
| 3 (independent re-run) | 61.1 | 77.3 | 100% (474/474) |

The headline is run-independent: **every run met the 100 ms Near-RT RIC budget on
100% of episodes**. The gate-on vs gate-off difference within any single run is
smaller than the variation between runs, so the Safety Gate adds no measurable
overhead. Data: `results/tables/latency_reproducibility_runs.csv` (report Table 10).

---

## Baselines

| Baseline | What it is | Difference vs H-TRACE |
|---|---|---|
| **Tsourdinis et al. (ACM MobiCom 2024)** | ML (Isolation Forest) 5G anomaly detection — public code | no LSTM layer, no hierarchy, **no Safety Gate** |
| **OCSVM** | One-Class SVM anomaly detector | no forecasting / hierarchy / gate |
| **Threshold** | rolling z-score detector | classic pre-ML monitoring |
| **Persistence / Seasonal-Naive** | model-free forecasters | forecasting comparison for the LSTM |
| **H-TRACE NoGate** | ablation: H-TRACE with the Safety Gate disabled | isolates the gate's contribution |
| **Habib et al. HODT** | hierarchical decision transformer (literature only) | 11.5% false-pass; no public code |
