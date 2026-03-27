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

## Recommended Run (One Command)

From project root:

```bash
./run_all.sh
```

This starts:
- FastAPI backend
- Collector agent
- Master agent
- Diagnosis agent
- Scheduling agent
- Engagement agent
- Service completion agent
- All required Celery workers (queue-specific)

To stop everything:
- Press `Ctrl+C` in the same terminal.

## Health Check

```bash
curl -sS http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Manual Startup (Fallback)

Use these commands from project root if you want to run components separately.

Backend:

```bash
PYTHONPATH=. ./AutoAI_ENV/bin/python -m uvicorn backend.main:app --port 8000
```

Agents:

```bash
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/collector_agent.py
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/master_agent.py
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/diagnosis_agent.py
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/scheduling_agent.py
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/engagement_agent.py
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/service_completion_agent.py
```

Celery workers:

```bash
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q diagnosis_queue -n diagnosis_queue_worker@%h
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q execution_diagnosis_task_queue -n execution_diagnosis_queue_worker@%h
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q scheduling_queue -n scheduling_queue_worker@%h
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker --loglevel=info --pool=threads --concurrency=4 --queues=engagement_queue -n engagement_queue_worker@%h
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q service_completion_queue -n service_completion_queue_worker@%h
```

## Troubleshooting

### 1) `python: command not found`
Use explicit interpreter:

```bash
./AutoAI_ENV/bin/python ...
```

### 2) Mongo TLS/certificate errors
Ensure your system CA setup is valid and `.env` uses a valid Mongo connection string.
The one-command launcher also applies certificate path handling at runtime.

### 3) Celery worker conflicts / duplicate node names
Use the exact worker commands above with `-n` unique worker names.

### 4) Backend not reachable on port 8000
Check if another process is already bound:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

## Notes

- The project currently uses polling-based agents plus Celery queue execution.
- The one-command launcher is the easiest way for demo and development runs.
- For phase-specific command updates, see `phase_runbook.md`.
