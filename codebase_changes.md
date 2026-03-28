# Codebase Changes Log

Purpose:
- Track all major changes made to the original codebase to support the frontend.
- Keep changes grouped by implementation phase.
- Preserve auditability for hackathon demo prep.

Working rule (locked):
- Before changing any existing backend/agent/worker file, explicit user confirmation will be requested.
- New files/folders for frontend-only work can proceed inside FRONTEND/ once execution starts.

Current session override:
- User granted full permission to proceed phase-by-phase without repeated prompts.

Change logging format:
- Date:
- Phase:
- Area:
- Files changed:
- What changed:
- Why changed:
- Risk/impact:
- Validation done:

---

## Phase A - Foundation

### 2026-03-27 - Activity logging foundation + realtime stream
- Date: 2026-03-27
- Phase: A (Foundation)
- Area: Backend activity logging, metrics surface, websocket stream
- Files changed:
	- backend/main.py
	- backend/routes/activity.py
	- backend/activity/__init__.py
	- backend/activity/event_bus.py
	- backend/activity/service.py
	- backend/activity/helpers.py
- What changed:
	- Added new activity module with reusable event builder, event persistence service, lazy index creation, and best-effort helper API.
	- Added in-process pub/sub event bus for live websocket fanout.
	- Added new API router under /api/activity with endpoints:
		- POST /api/activity/log
		- GET /api/activity/events
		- GET /api/activity/vehicle/{vehicle_id}
		- GET /api/activity/metrics/overview
		- WS /api/activity/ws
	- Wired activity router into FastAPI app bootstrap.
- Why changed:
	- Phase A requirement: establish universal event logging foundation and realtime stream support for upcoming frontend dashboards.
- Risk/impact:
	- Additive change only; existing routes remain untouched.
	- New Mongo collection activity_events introduced with indexes for timeline/filter query performance.
	- WebSocket stream is in-process and suitable for hackathon/demo scale.
- Validation done:
	- Ran syntax compile check:
		- /Users/rudrarajpurohit/Desktop/EY/AutoAI/.venv/bin/python -m compileall backend/activity backend/routes/activity.py backend/main.py
	- Result: all modified/new files compiled successfully.

### 2026-03-27 - Runtime stabilization + one-command boot
- Date: 2026-03-27
- Phase: A (Foundation) runtime hardening checkpoint
- Area: Environment/runtime boot reliability
- Files changed:
	- agents/diagnosis_agent.py
	- worker_tasks/engagement_tasks.py
	- run_everything.py
	- run_all.sh
- What changed:
	- Fixed a syntax corruption in diagnosis agent rollback payload (`isoformat` typo).
	- Made engagement task resilient when CrewAI LLM init fails (graceful fallback to mock flow instead of import-time crash).
	- Added unified launcher `run_everything.py` that:
		- loads env from backend/.env safely,
		- sets TLS cert path for Atlas connectivity,
		- starts backend + agents + all Celery workers in required order,
		- applies clean-start preflight process cleanup,
		- assigns unique Celery worker node names,
		- performs health wait and coordinated shutdown.
	- Added shell one-liner entrypoint `run_all.sh`.
- Why changed:
	- Existing documented commands were failing due interpreter/path/env drift and process collision; launcher makes runtime deterministic for demo use.
- Risk/impact:
	- Additive utility scripts; no functional lifecycle logic redesign.
	- Engagement path now degrades gracefully instead of hard-crashing when provider config is unavailable.
- Validation done:
	- `./AutoAI_ENV/bin/python -m compileall run_everything.py worker_tasks/engagement_tasks.py agents/diagnosis_agent.py`
	- `./run_all.sh` smoke run confirmed backend health and active multi-agent/celery traffic logs.

### 2026-03-27 - Phase A e2e test hardening fixes
- Date: 2026-03-27
- Phase: A (Foundation) e2e validation
- Area: Activity API correctness + websocket realtime delivery
- Files changed:
	- backend/activity/service.py
	- phase_a_e2e_test.sh
	- phase_runbook.md
- What changed:
	- Fixed `POST /api/activity/log` internal server error by preventing `ObjectId` mutation leakage into response payload.
	- Enabled websocket publish from sync contexts by adding `asyncio.run(...)` fallback when no running loop exists.
	- Added reusable Phase A endpoint test script and runbook validation commands.
- Why changed:
	- Phase A endpoints persisted data but failed one response serialization case and missed realtime broadcast in sync call paths.
- Risk/impact:
	- Minimal and localized to activity service behavior.
	- Improved reliability for frontend realtime feed.
- Validation done:
	- `./phase_a_e2e_test.sh` passed all 5 HTTP checks.
	- websocket e2e check passed (`POST status: 200` and expected event received on `/api/activity/ws`).

---

## Phase B - Backend Coverage

### 2026-03-27 - Backend coverage instrumentation + summaries + richer metrics
- Date: 2026-03-27
- Phase: B (Backend Coverage)
- Area: Route/agent/worker instrumentation, summary pipeline, dashboard metrics
- Files changed:
	- backend/routes/activity.py
	- backend/activity/service.py
	- backend/routes/telemetry.py
	- backend/routes/put_diagnosis.py
	- backend/routes/put_diagnosis_job.py
	- backend/routes/put_done_diagnosis.py
	- backend/routes/schedule.py
	- backend/routes/service.py
	- backend/routes/vehicle_state.py
	- agents/master_agent.py
	- worker_tasks/diagnosis_tasks.py
- What changed:
	- Added summary endpoints:
		- POST /api/activity/summary/{vehicle_id}
		- GET /api/activity/summary/{vehicle_id}
	- Added deterministic technical/business/judge summary generation from activity timeline events and persisted summaries in `activity_summaries`.
	- Expanded metrics overview payload with fleet stage counts, active/high-risk vehicle counts, events/min, and stale/failed event counters for mission-control cards.
	- Wired activity instrumentation into key API transition points (telemetry ingestion, diagnosis queue/finalization, scheduling updates, service completion, vehicle-state transitions).
	- Added agent-level activity emits in `master_agent` for gate decisions and enqueue success/failure.
	- Added worker-level activity emits in `diagnosis_tasks` for start/precheck/stale-abort/queue-success/queue-failure.
	- Added `activity_summaries` indexes for fast vehicle summary reads.
- Why changed:
	- Phase B requirement: provide complete backend observability coverage and a narrative summary layer that the frontend can render as a live, high-signal operational story.
- Risk/impact:
	- Primarily additive instrumentation; no route removals or schema-breaking API changes.
	- New counters are derived from existing collections and may reflect current runtime state noise in dev environments.
- Validation done:
	- Syntax check:
		- `/Users/rudrarajpurohit/Desktop/EY/AutoAI/.venv/bin/python -m compileall backend/routes/activity.py backend/routes/telemetry.py backend/routes/put_diagnosis.py backend/routes/put_diagnosis_job.py backend/routes/put_done_diagnosis.py backend/routes/schedule.py backend/routes/service.py backend/routes/vehicle_state.py backend/activity/service.py agents/master_agent.py worker_tasks/diagnosis_tasks.py`
	- Regression check:
		- `./phase_a_e2e_test.sh` passed.
	- New endpoint checks:
		- `POST /api/activity/summary/V_PHASE_A` returned generated summaries.
		- `GET /api/activity/summary/V_PHASE_A` returned persisted summary document.
		- `GET /api/activity/metrics/overview?window_events=100` returned enhanced metrics fields.

---

## Phase C - Frontend Core

### Pending
- No changes logged yet.

---

## Phase D - Advanced Demo Features

### Pending
- No changes logged yet.

---

## Phase E - Hardening

### Pending
- No changes logged yet.

---

## Notes
- Only major codebase changes will be logged here.
- Minor cosmetic formatting-only edits may be omitted unless they affect behavior.
