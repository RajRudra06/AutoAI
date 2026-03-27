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

---

## Phase B - Backend Coverage

### Pending
- No changes logged yet.

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
