# AutoAI — Autonomous Vehicle Service Orchestration Platform

**AutoAI** is a multi-agent, queue-driven platform that autonomously orchestrates the complete vehicle service lifecycle — from raw sensor telemetry to anomaly detection, diagnosis, service booking, customer engagement, and service completion.

The system continuously monitors a simulated vehicle fleet, detects emerging issues with an ML anomaly-detection model, and drives every vehicle through a well-defined service lifecycle — all while emitting a complete, human-readable audit trail of every decision and action.

Built for the **ET AI Hackathon 2026** problem statement.

---

## What It Does

1. **Telemetry Ingestion** — A collector agent continuously generates realistic sensor telemetry (engine temp, oil pressure, brake wear, battery health, vibration, etc.) for a simulated fleet.
2. **Health Screening** — A master agent evaluates every telemetry snapshot with rule-based health gates and flags vehicles that need attention.
3. **ML Diagnosis** — A trained **Isolation Forest** model scores 43 engineered vehicle-health features per vehicle and classifies risk as **HIGH** or **LOW**.
4. **Service Scheduling** — High-risk vehicles are automatically booked into a service slot at a service center.
5. **Customer Engagement** — An LLM agent (CrewAI + Groq) generates a personalized customer message describing the issues and the booking, delivered via email.
6. **Service Completion** — Once the booking is completed, the vehicle lifecycle is closed and the vehicle returns to `IDLE`, ready for the next telemetry cycle.
7. **Observability** — Every stage transition, decision, and worker execution is recorded as a structured activity event, exposed via live WebSocket streams, metrics dashboards, and per-vehicle journey summaries.

---

## Architecture at a Glance

AutoAI splits the system into two intentionally separated layers:

- **Decision Layer (Agents)** — Lightweight polling agents that inspect system state, enforce lifecycle gates, detect stale work, and decide *what* should happen next.
- **Execution Layer (Celery Workers)** — Asynchronous workers that do the heavy lifting (ML inference, bookings, email) on dedicated Redis queues, and re-validate task ownership before executing anything.

All state lives in a single MongoDB source of truth, and **every component — agent or worker — communicates exclusively through the FastAPI backend**. Nothing mutates workflow state directly.

```
         ┌────────────────────────────────────────────────────────────┐
         │                        FASTAPI BACKEND                     │
         │              (state · lifecycle gates · observability)     │
         └──────▲────────────────────▲───────────────────▲───────────┘
                │                    │                   │
      ┌─────────┴──────┐   ┌─────────┴──────────┐   ┌────┴──────────────┐
      │ DECISION LAYER │   │  EXECUTION LAYER   │   │      STORAGE      │
      │     Agents     │──▶│  Celery Workers    │──▶│  MongoDB + Redis  │
      │ master         │   │  (ML inference,    │   │  (source of truth)│
      │ diagnosis      │   │   booking, email)  │   │  (queues/broker)  │
      │ scheduling     │   │  5 dedicated queues│   │                   │
      │ engagement     │   │                    │   │                   │
      │ service close  │   │                    │   │                   │
      └────────────────┘   └────────────────────┘   └───────────────────┘
```

### Vehicle Lifecycle State Machine

```
IDLE ──▶ DIAGNOSIS_PENDING ──▶ DIAGNOSIS_COMPLETE ──▶ SCHEDULING_COMPLETE ──▶ ENGAGEMENT_COMPLETE ──▶ IDLE
         (job created)          (ML: HIGH risk)       (booking created)       (LLM email sent)      (lifecycle reset)

               │  ML: LOW risk ──────────────────────▶ IDLE  (no service needed)
               │  skip / fail / stale ───────────────▶ IDLE  (safe rollback)
```

Every agent enforces strict lifecycle gates and stale-task detection (tasks older than 60 seconds are revoked and the vehicle is reset to a safe baseline), and Celery retries failed tasks with exponential backoff — making the system self-healing under failure.

---

## Tech Stack

| Layer            | Technology                                                            |
| ---------------- | --------------------------------------------------------------------- |
| Backend API      | Python · FastAPI · WebSockets                                         |
| Data Store       | MongoDB (source of truth, 10 collections)                             |
| Task Queue       | Celery + Redis (5 dedicated queues, late acks, retries with backoff)  |
| ML Model         | scikit-learn Isolation Forest (unsupervised anomaly detection)        |
| Agents           | Python multiprocessing + hash-based sharding + thread pools           |
| LLM Engagement   | CrewAI + Groq (llama-3.1-8b-instant) with template-based fallback     |
| Email            | SMTP (Gmail)                                                          |
| Frontend         | Next.js dashboard (mission control + live telemetry)                 |

---

## Repository Structure

```
├── backend/             # FastAPI app — routes, middleware, DB, activity/observability
│   ├── routes/          # Telematics, vehicles, diagnosis, scheduling, engagement, activity…
│   ├── activity/        # Event bus, event store, metrics, journey summaries
│   └── raw_data_generator.py  # Synthetic telemetry simulator
├── agents/              # Decision-layer orchestrators (collector, master, diagnosis,
│                        #   scheduling, engagement, service completion)
├── worker_tasks/        # Celery tasks (diagnosis, ML execution, scheduling, engagement,
│                        #   service completion) + celery_config.py
├── helpers/             # Feature engineering, health gates, risk scoring, email, slots
├── diag_agent_model/    # Trained Isolation Forest artifacts (joblib) + training notebook
├── frontend/            # Next.js mission-control dashboard
├── run_all.sh           # Shell entrypoint
└── run_everything.py    # One-command launcher — orchestrates full stack lifecycle
```

---

## Getting Started

### Prerequisites

- Python 3.13
- Redis running locally on `localhost:6379`
- MongoDB (local or Atlas)

### 1. Environment Setup

Create `backend/.env`:

```env
MONGO_URL=mongodb://localhost:27017/autoai
BACKEND_API_URL=http://127.0.0.1:8000
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
GROQ_API_KEY=your_groq_api_key
EMAIL_USER=your_email@gmail.com
GOOGLE_APP_PASSWORD=your_app_password
```

### 2. Run the Backend Stack

```bash
source AutoAI_ENV/bin/activate
./run_all.sh
```

`run_all.sh` boots the entire ecosystem in the correct order, monitors every process, and shuts everything down cleanly on exit:

1. FastAPI backend on port `8000` (waits for `/health`)
2. Collector agent → Master agent → Diagnosis worker/agent → ML execution worker → Scheduling agent/worker → Engagement agent/worker → Service-completion agent/worker

```bash
curl -sS http://127.0.0.1:8000/health
# {"status":"ok"}
```

### 3. Run the Dashboard (optional)

```bash
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

---

## Observability

Every stage transition, gate decision, and worker run is logged as a structured event. AutoAI exposes:

- **Live event stream** — WebSocket feed of activity events as they happen
- **Fleet metrics** — throughput, fleet stage distribution, high-risk counts, transition counts
- **Queue & worker health** — Redis queue depths, worker heartbeats, latency trends
- **Journey summaries** — per-vehicle technical, business, and audit-friendly narrative summaries of the complete lifecycle

---

## License

MIT — see `LICENSE`.