# AutoAI - Multi-Agent Vehicle Lifecycle System

AutoAI is an end-to-end multi-agent backend that simulates telemetry ingestion, anomaly diagnosis, scheduling, engagement, and service completion for vehicles.

The project includes:
- FastAPI backend
- MongoDB-backed lifecycle state
- Multiple orchestrator agents
- Celery workers + Redis queues
- Isolation Forest-based diagnosis flow

## Repository Structure

- `backend/` FastAPI API, routes, middleware, DB connection
- `agents/` decision/orchestration agents
- `worker_tasks/` Celery task execution layer
- `helpers/` feature engineering and utility logic
- `diag_agent_model/` trained model artifacts
- `run_everything.py` one-command launcher for full stack
- `run_all.sh` shell entrypoint for one-command launcher
- `phase_runbook.md` phase-wise run and test command tracker

## Prerequisites

- macOS/Linux
- Python 3.13
- Redis running locally on default port `6379`
- MongoDB connection string available

## Environment Setup

Create/update `backend/.env` with valid key-value pairs (one per line):

```env
MONGO_URL=your_mongodb_connection_string
BACKEND_API_URL=http://127.0.0.1:8000
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
GROQ_API_KEY=your_groq_api_key
EMAIL_USER=your_email
GOOGLE_APP_PASSWORD=your_app_password
```

Important:
- Keep `.env` lines in strict `KEY=VALUE` format.
- Do not add plain words or malformed lines in `.env`.

## Quick Start (Two-Terminal Setup)

Follow these steps to launch the entire AutoAI ecosystem in under 60 seconds.

### 1. Terminal 1: Agentic Backend & Orchestration
This terminal handles the FastAPI server, MongoDB persistence, and the multi-agent decision layers.

```bash
# Activate the virtual environment
source AutoAI_ENV/bin/activate

# Launch the full-stack agentic engine
./run_all.sh
```

**What this starts:**
- **FastAPI Core**: The central API gateway.
- **Agent Cluster**: Master, Diagnosis, Scheduling, Engagement, and Service agents.
- **Worker Layer**: All queue-specific Celery workers for autonomous execution.

---

### 2. Terminal 2: Mission Control Dashboard
This terminal handles the high-fidelity Next.js frontend simulation.

```bash
cd frontend

# Clean stale builds and ensure dependencies are synchronized
rm -rf .next
npm install

# Launch the interactive simulation dashboard
npm run dev
```

**Access the Dashboard:**
Navigate to [http://localhost:3000](http://localhost:3000) to begin the vehicle lifecycle simulation.

---

## Health Check

To verify the backend engine is responsive, run:

```bash
curl -sS http://127.0.0.1:8000/health
# Expected: {"status":"ok"}
```

## Troubleshooting

### 1) Environment Activation
If `source AutoAI_ENV/bin/activate` fails, ensure the `AutoAI_ENV` directory exists in your project root. If missing, recreate the environment:
```bash
python3 -m venv AutoAI_ENV
source AutoAI_ENV/bin/activate
pip install -r requirements.txt # If absolute manually
```

### 2) Port Conflicts
If port `8000` (Backend) or `3000` (Frontend) is already in use, find and terminate the process:
```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

### 3) MongoDB Connectivity
Ensure your `.env` contains a valid `MONGO_URL`. The `run_all.sh` script automatically handles certificate path resolution for secure connections.

---

## Technical Architecture Notes
- **State Management**: Indirect agent communication via FastAPI + MongoDB.
- **Task Execution**: Decision/Execution separation using Redis-backed Celery queues.
- **Simulation**: High-fidelity frontend state machine mimicking real-time backend telemetry.
