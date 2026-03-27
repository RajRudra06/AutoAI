# AutoAI Hackathon Build Plan (Backend + Frontend + Demo)

This file is the execution contract for the full implementation.
Nothing starts until user says: START.

## 1. Goal
Build a complete, demo-ready frontend experience for the existing agentic backend so that one vehicle journey is visible in real time across all agents and stages, with replay, summarization, and operational observability.

## 2. Scope Commitment
Everything below is in-scope and will be implemented:

- Core demo story flow visualization
- Mission control dashboard
- Vehicle journey screen with stage progression
- Live event feed
- Queue and worker health view
- Diagnosis explainability panel
- Engagement intelligence panel
- CrewAI journey summaries
- Replay mode
- Incident and stale recovery panel
- Logger API and event schema
- WebSocket real-time stream
- Backend instrumentation at key transition points
- Frontend polish for hackathon demo recording

## 3. Core Demo Story (Must Be Fully Visible)
A single vehicle must be trackable through this exact chain:

1. Telemetry arrives
2. Master decides diagnosis required
3. Diagnosis job queued and picked
4. Diagnosis execution + risk result
5. Scheduling booking created
6. Engagement message generated/sent
7. Service completion closes lifecycle
8. Journey summary generated in plain language

## 4. Frontend Product Surfaces

### 4.1 Mission Control Screen
Show:
- Fleet-level stage counts (IDLE, DIAGNOSIS_PENDING, DIAGNOSIS_COMPLETE, SCHEDULING_COMPLETE, ENGAGEMENT_COMPLETE)
- Active high-risk count
- Current in-progress vehicles
- Error/stale events count
- Live throughput counters (events/min, tasks completed)

### 4.2 Vehicle Journey Screen (Hero)
Show:
- One selected vehicle pipeline lane: Collector -> Master -> Diagnosis -> Scheduling -> Engagement -> Service Completion
- Current owner (agent/task)
- Stage start time + elapsed time
- Task IDs, job IDs, last event
- Animated progression token
- Status chips (success, pending, failed, stale)

### 4.3 Agent Activity Feed
Show:
- Streaming event timeline
- Filters: vehicle_id, source, stage, status, severity
- Expandable details JSON for each event

### 4.4 Queue and Worker Health
Show:
- Queue depth by queue name
- Task execution success/failure/retry trend
- Average wait time and run time
- Worker heartbeat/last-seen

### 4.5 Diagnosis Explainability Panel
Show:
- Latest anomaly_score, risk_score, risk_level
- Top contributing 7d feature anomalies (from available features/rules)
- Short reason text for why action was taken

### 4.6 Engagement Intelligence Panel
Show:
- Final generated customer message
- Delivery/log status
- Risk context
- Summary of customer-facing action

### 4.7 Replay Mode
Show:
- Select vehicle and time window
- Replay all lifecycle events in order
- Speed controls (1x/2x/4x)
- Pause/resume step-through

### 4.8 Incident and Recovery Panel
Show:
- Stale task detection events
- Resets/revocations
- Failure reasons
- Recovery outcome status

## 5. Universal Logger API Design

### 5.1 Event Schema
Every logged event should contain:
- event_id
- timestamp
- vehicle_id
- source_type (agent | worker | api | system)
- source_name
- stage_from
- stage_to
- action
- status (success | failed | skipped | stale | retried | info)
- celery_task_id (optional)
- job_id (optional)
- risk_level (optional)
- summary
- details (dict)
- latency_ms (optional)

### 5.2 Backend Event Endpoints
To implement:
- POST /api/activity/log
- GET /api/activity/events (with filters + pagination)
- GET /api/activity/vehicle/{vehicle_id}
- GET /api/activity/metrics/overview

### 5.3 Real-Time Push
To implement:
- WebSocket endpoint for live events (publish on every new log)
- Broadcast model suitable for frontend dashboard streaming

## 6. Backend Instrumentation Points (Must Log)

### 6.1 API Layer
- telemetry receive
- diagnosis queue create/start/skip/fail/complete
- schedule create/fetch/complete
- vehicle state transitions
- feedback log
- engagement log

### 6.2 Agent Layer
- master gate decision
- diagnosis gate decision
- scheduling gate decision
- engagement gate decision
- service completion gate decision
- all enqueue attempts + results
- stale reset attempts + outcomes

### 6.3 Worker Task Layer
- task started
- pre-check pass/fail
- model inference completed
- booking created
- engagement generated
- service completed
- retries/failures

## 7. CrewAI Summarization Layer

### 7.1 Summary Types
Generate and expose:
- Technical summary (ops + transitions + retries)
- Business summary (impact narrative)
- Judge-friendly short summary (30-60 words)

### 7.2 Endpoints
To implement:
- POST /api/activity/summary/{vehicle_id}
- GET /api/activity/summary/{vehicle_id}

## 8. Frontend Tech and App Structure
Preferred implementation:
- Next.js + TypeScript
- Recharts (or equivalent) for metrics
- Framer Motion for meaningful animation
- WebSocket client for live updates
- Clean design tokens with custom visual theme

Mandatory repository structure and isolation requirement:
- All frontend code must live only under a new root folder: FRONTEND/
- FRONTEND/ must be fully independent from the backend/agent codebase
- No sharing of backend package files, configs, lockfiles, build scripts, or runtime assets
- FRONTEND/ must have its own package.json, dependency tree, scripts, and env handling
- FRONTEND/ must be deployable independently (target: Vercel)
- Treat FRONTEND/ as a standalone product that can be moved to another repository without refactor

App sections:
- /dashboard (mission control)
- /vehicle/:id (journey hero)
- /replay/:id (replay mode)
- /incidents (stale/failure view)

## 9. Visual Direction (Hackathon Demo First)
- Non-generic control-room interface
- Black professional theme as primary visual direction
- Distinct stage colors (ingest blue, diagnosis amber, risk red, recovery orange, complete green)
- Animated transitions for state changes
- Responsive desktop + mobile support
- Recording-friendly contrast and readability

Mandatory UI behavior requirement:
- The dashboard must feel dynamic and alive (real-time transitions, timeline movement, state pulses)
- Avoid static-looking layouts that feel like a dump of synthetic data
- Surface causality and progression (what happened, why it happened, what is next)
- Prefer narrative visualizations over raw tables wherever possible
- Frontend must look modern, dense, and feature-rich (not a minimal old-style website)
- Use layered panels, rich telemetry cards, and purposeful motion to communicate complexity
- Avoid generic template-like layouts
- Login/logout/user-auth pages are out of scope for hackathon build unless explicitly requested later

## 10. Execution Phases

Total phases for full delivery: 5

Phase list:
- Phase A: Foundation
- Phase B: Backend Coverage
- Phase C: Frontend Core
- Phase D: Advanced Demo Features
- Phase E: Hardening

### Phase A: Foundation
- Create activity logging collection + API
- Add WebSocket event streaming
- Add instrumentation helpers

### Phase B: Backend Coverage
- Wire logging into routes, agents, workers
- Add summary generation pipeline and storage
- Add metrics endpoints for dashboard cards/charts

### Phase C: Frontend Core
- Build app scaffold and layout system
- Build mission control and live feed
- Build vehicle journey view

### Phase D: Advanced Demo Features
- Build replay mode
- Build queue/worker health panel
- Build incidents/recovery panel
- Build summary panel

### Phase E: Hardening
- Integrate run instructions and fallback handling
- Validate with one full lifecycle scenario
- Polish visuals for demo recording

## 11. Acceptance Checklist
All must be true before done:

- A vehicle can be tracked live end-to-end in UI
- Each stage change is visible and timestamped
- Event feed updates in real time
- Replay reproduces completed journeys
- Summary panel explains journey in natural language
- Failures/stale resets are visible in incident panel
- Dashboard reflects live counts and metrics
- Demo run can be recorded without manual patching

## 12. Constraints and Non-Goals
- No major replacement of your existing backend architecture
- Focus on additive instrumentation and presentation
- Keep existing lifecycle semantics intact
- Frontend must be developed only inside FRONTEND/ at repository root
- Frontend and backend must remain decoupled at package/project level
- Frontend should consume backend only through APIs/WebSockets, not shared code imports

## 13. Start Protocol
When user says START:
1. Begin Phase A immediately
2. Commit in small coherent checkpoints
3. Keep backend stable while adding frontend
4. Validate after each phase

---
Prepared for execution.
Status: READY, WAITING FOR START.
