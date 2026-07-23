# H-TRACE — Demonstrator Application (Flask/SocketIO + React)

Interactive demonstrator for the H-TRACE neurosymbolic O-RAN controller. It replays
the Network Operator KPI dataset live and streams, per region, the KPI series,
Isolation-Forest detections, edge decisions and Safety-Gate verdicts, with operator
chat routed through the Gemini Regional Coordinator.

Corresponds to the demonstrator deliverable described in Sections 4.7 and 5 of the report.

---

## Requirements

- **Python 3.12**
- **Node.js 18+** (tested on Node 24)
- A **Google Gemini API key** (optional — see note below)

---

## 1. Backend (Flask + SocketIO)

> **Important:** the backend must be started from **inside the `server/` folder**.
> Its modules use flat imports (e.g. `from timeutil import utcnow`), so running it
> from `2_Application/` will fail with `ModuleNotFoundError: No module named 'timeutil'`.

```bash
cd server
pip install -r requirements.txt
python app.py
```

The API and WebSocket server start on **http://localhost:8000**
(override with the `PORT` environment variable).

On startup it prints a banner confirming which tiers loaded, e.g.:

```
  AI · Smart Manager (Principal) : OK
  Google ADK                     : OK
  Gemini (AI tier)               : OK
  ML Local Teams                 : Isolation Forest + LSTM
  Symbolic Safety Gate           : Deterministic (0% false-pass)
```

### API key

The `.env` file lives in **this folder (`2_Application/`)**, next to `.env.example` —
not inside `server/`. The backend loads it automatically when started from `server/`.

```bash
# from 2_Application/
copy .env.example .env      # Windows
cp .env.example .env        # macOS/Linux
```

Then set `GOOGLE_API_KEY=<your key>` in `.env`
(get one free at <https://aistudio.google.com/apikey>).

`.env` must never be committed or shared. **If no key is set the application still
runs** — the Coordinator falls back to a deterministic keyword intent mapper, so the
ML tiers and the Safety Gate work exactly as described in the report.

---

## 2. Frontend (React + Vite)

In a **second terminal**:

```bash
cd client
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies `/api` and `/socket.io`
to the backend on port 8000, so start the backend first.

For a production build:

```bash
npm run build     # outputs to client/dist/
npm run preview
```

---

## 3. What to look at in the demo

| View | What it shows |
|------|---------------|
| **Dashboard / Streaming telemetry** | Live KPI replay per region with Isolation-Forest anomaly flags |
| **Scenario control** | Switch between the three scenarios: Night, Festival, Self-Healing |
| **Issue command centre / Resolution timeline** | Edge decisions and the action taken per detected fault |
| **Safety-Gate verdicts** | Every proposed action with PASS/BLOCK and the **rule identifier that fired** — the audit trail |
| **Chat interface** | Type a plain-language operator request; the Gemini Coordinator maps it to one of `save_energy` / `max_capacity` / `heal` |

The Safety Gate is deterministic: the same action and state always produce the same
verdict, and every block is logged with its rule ID.

---

## Layout

```
2_Application/
  server/            Flask + SocketIO backend  (run app.py from HERE)
    app.py             API + WebSocket entrypoint (port 8000)
    scenario_engine.py live replay + scenario switching
    agent_bridge.py    bridge to the ADK agent layer
    gemini_service.py  Gemini intent translation
    data_loader.py     KPI dataset replay
    timeutil.py        shared time helper
  agents/            Google ADK agent hierarchy
    principal_agent/           Smart Manager (non-real-time)
    regional_coordinator/      Coordinator + edge agents
      edge_agents/             monitoring / prediction / decision / action / learning
    htrace_core.py             detector + predictor + Safety Gate core
  client/            React + Vite dashboard (port 5173)
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'timeutil'` | You started the backend from the wrong folder — `cd server` first |
| Dashboard loads but no data | Backend isn't running, or not on port 8000 |
| `Gemini (AI tier): Not available` in the banner | No `GOOGLE_API_KEY` found in `2_Application/.env` — the app still runs with the keyword fallback |
| `torch` install is very large | CPU-only wheel: `pip install torch --index-url https://download.pytorch.org/whl/cpu` |
