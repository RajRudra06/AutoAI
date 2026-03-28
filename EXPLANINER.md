# AutoAI Project Explainer

## 1. What This Project Does (Plain-English Summary)

AutoAI is an end-to-end autonomous vehicle service orchestration platform.

Its main purpose is to:
- Continuously ingest vehicle telemetry.
- Decide when a vehicle needs diagnosis.
- Run anomaly/risk inference.
- Schedule service appointments.
- Generate customer engagement communication.
- Close the service lifecycle.
- Expose complete operational visibility through APIs and realtime activity streams for a control-room frontend.

In short:
AutoAI automates the path from raw sensor data to service action, while preserving auditability and human-readable lifecycle traceability.

---

## 2. Core Idea: Decision Layer vs Execution Layer

The architecture is intentionally split into two roles:

1. Decision Layer (Agents)
- Agents poll system state and decide what should happen next.
- Agents enforce lifecycle gates, stale-checks, and transition eligibility.
- Agents enqueue tasks when a stage should execute.

2. Execution Layer (Celery Workers)
- Workers run the heavy/operational work asynchronously.
- Workers re-validate ownership before execution.
- Workers call backend APIs to write durable state transitions.

Why this split matters:
- Better reliability: stale tasks can be blocked/reset.
- Better scalability: CPU/model/email/booking work runs in queue workers.
- Better observability: each layer can emit activity events.

---

## 3. End-to-End Architecture (Frontend to DB)

### 3.1 Runtime Components
- Frontend (Next.js): live control-room and vehicle journey views.
- Backend (FastAPI): central state/API/control plane.
- Agents (Python processes): orchestration and gating.
- Celery Workers: async stage execution.
- Redis: message broker/result backend for Celery.
- MongoDB: source-of-truth data store.

### 3.2 System Interaction Model
1. Frontend and internal services call backend APIs.
2. Backend reads/writes MongoDB and returns state.
3. Agents poll backend state endpoints.
4. Agents enqueue Celery tasks to Redis queues.
5. Workers consume queue jobs, execute logic, and write back via backend APIs.
6. Backend activity service emits timeline events, metrics, and websocket updates.

### 3.3 Backend as Integration Layer
Backend is the mandatory integration contract for:
- Agents
- Workers
- Frontend

No component directly mutates workflow state in Mongo except through backend route contracts (except a few direct writes in backend routes by design). This keeps lifecycle transitions centralized and traceable.

---

## 4. Authentication and Access Model

Current implementation is API-key header auth middleware, not JWT.

Auth mechanism:
- Required headers for /api endpoints:
  - X-AGENT-ID
  - X-API-KEY
- Valid pairs are hardcoded in middleware.

Health endpoint is open:
- /health bypasses auth.

Important clarification:
- If you describe this externally, be accurate: current auth is static header key auth, not JWT token verification.
- JWT can be introduced later, but it is not yet implemented in this repository.

---

## 5. Data Model and Collections (MongoDB)

The following collections are actively used:

1. telemetry
- Raw periodic telemetry snapshots.
- Fields include vehicle_id, telemetryID, features, status.

2. vehicle_state
- Current orchestrated state per vehicle.
- Includes:
  - latest and previous features
  - pipeline_associated (status, assigned_at, celery_task_id)
  - workflow_state (current_stage, flags)
  - risk_state (high_risk_active, unresolved_issues)
  - processing timestamps

3. diagnosis_jobs
- Diagnosis work items with statuses:
  - PENDING
  - IN_PROGRESS
  - COMPLETED
  - COMPLETED_SKIPPED
  - FAILED
  - STALE_JOB

4. predictions
- Model output snapshots with risk/anomaly metadata.

5. bookings
- Service appointments and booking state.

6. engagements
- Engagement message logs.

7. feedback
- Service completion / final feedback records.

8. ueba_logs
- Security/behavior escalation events.

9. activity_events
- Unified observability event stream.

10. activity_summaries
- Generated technical/business/judge summaries by vehicle.

---

## 6. Queue Topology and Celery Routing

Redis-backed Celery queues:

1. diagnosis_queue
- Task family: tasks.diagnosis.*
- Worker module: worker_tasks/diagnosis_tasks.py
- Purpose: master-triggered diagnosis queueing stage.

2. execution_diagnosis_task_queue
- Task family: tasks.execute_diagnosis.*
- Worker module: worker_tasks/execution_diagnosis_task.py
- Purpose: actual model inference and diagnosis completion logic.

3. scheduling_queue
- Task family: tasks.execute_scheduling.*
- Worker module: worker_tasks/scheduling_tasks.py
- Purpose: slot generation, booking, scheduling state transitions.

4. engagement_queue
- Task family: tasks.execute_engagement.*
- Worker module: worker_tasks/engagement_tasks.py
- Purpose: customer communication generation and send/log/update.

5. service_completion_queue
- Task family: tasks.execute_service_completion.*
- Worker module: worker_tasks/service_completion_tasks.py
- Purpose: booking closure + lifecycle reset + feedback log.

Celery reliability defaults include:
- retries
- backoff
- jitter
- acks_late
- task_reject_on_worker_lost
- prefetch_multiplier=1

---

## 7. Backend API Layers

### 7.1 Control/State APIs
- telemetry ingestion
- vehicle state get/update
- diagnosis queue/start/fail/complete/skip
- schedule book/get/update/complete
- engagement log
- feedback log
- service completion reset
- predictions storage/retrieval

### 7.2 Observability APIs
- POST /api/activity/log
- GET /api/activity/events
- GET /api/activity/vehicle/{vehicle_id}
- GET /api/activity/metrics/overview
- WS /api/activity/ws
- POST /api/activity/summary/{vehicle_id}
- GET /api/activity/summary/{vehicle_id}

These APIs are the foundation of the frontend control-room experience.

---

## 8. Agent-by-Agent Technical Breakdown

## 8.1 Collector Agent
Role:
- Produces rolling telemetry windows from generator logic.
- Extracts summarized features.
- Pushes to backend telemetry route.

Input:
- synthetic/raw generator window data.

Output:
- POST /api/telematics/data payloads.

Edge handling:
- per-vehicle send failures are logged and loop continues.

---

## 8.2 Master Agent (Primary Decision Gate)
Role:
- Polls all vehicle states.
- Runs diagnosis eligibility logic.
- Enqueues diagnosis task to diagnosis_queue.

Decision checks:
- diagnosis_required flag already set -> skip.
- needs_diagnosis(telemetry, previous_telemetry) -> trigger/no trigger.

Lifecycle gate blocks when:
- stage already advanced (DIAGNOSIS_PENDING/DIAGNOSIS_COMPLETE/SCHEDULING_COMPLETE/ENGAGEMENT_COMPLETE).
- high risk already active.
- last_processed_telemetry >= latest_feature_associated_telemetryID.
- pipeline currently assigned/non-initialized.

Stale reset behavior:
- If ASSIGNED_BY_MASTER_AGENT timeout exceeded while still effectively idle, revoke celery task and reset vehicle state to baseline.

Observability:
- Emits activity events for gate skip/no-trigger/trigger and enqueue success/failure.

---

## 8.3 Diagnosis Agent
Role:
- Polls diagnosis jobs.
- Applies lifecycle gate for diagnosis execution.
- Enqueues execution diagnosis worker task.

Lifecycle gate blocks when:
- vehicle already in later stages.
- stale/invalid telemetry ordering.
- pipeline ownership mismatch.

Special stale behavior:
- If vehicle stuck in ASSIGNED_BY_DIAGNOSIS_AGENT path beyond timeout, reset vehicle and mark job stale via finalize endpoint.

Queue output:
- execution_diagnosis_task_queue.

---

## 8.4 Scheduling Agent
Role:
- Polls vehicle states.
- Determines if scheduling stage should execute.
- Enqueues scheduling worker.

Gate checks:
- blocks if stage already scheduling complete/engagement complete.
- blocks on invalid telemetry ordering.
- blocks on pipeline mismatch.
- stale handling with task revoke + state reset.

Queue output:
- scheduling_queue.

---

## 8.5 Engagement Agent
Role:
- Polls vehicle states.
- Determines if engagement should execute.
- Enqueues engagement worker.

Gate checks:
- blocks if already engagement complete.
- blocks on telemetry ordering mismatch.
- blocks on ownership mismatch (must come from scheduling assignment).
- stale handling for ASSIGNED_BY_ENGAGEMENT_AGENT timeout.

Queue output:
- engagement_queue.

---

## 8.6 Service Completion Agent
Role:
- Polls vehicle states.
- Determines if final closure stage is eligible.
- Enqueues service completion worker.

Gate checks include:
- workflow not in ENGAGEMENT_COMPLETE.
- booking already completed.
- telemetry ordering mismatch.
- pipeline ownership mismatch.

Stale handling:
- revokes stale completion task and resets vehicle state.

Queue output:
- service_completion_queue.

---

## 8.7 UEBA Agent (Auxiliary / Incomplete)
Role intent:
- Behavioral/risk escalation logic.

Current status:
- Contains unresolved symbols and non-aligned endpoints (API_BASE/HEADERS references), so not production-ready in current form.
- Should be treated as experimental until refactored.

---

## 9. Worker-by-Worker Execution Breakdown

## 9.1 diagnosis_tasks (Queueing Worker)
Purpose:
- Validates ownership from master assignment.
- Calls diagnosis queue API.
- Updates temporary telemetry checkpoint.

Prechecks:
- must match ASSIGNED_BY_MASTER_AGENT and celery_task_id ownership.

Output:
- diagnosis job row creation + vehicle DIAGNOSIS_PENDING.

Observability:
- emits activity events for start, precheck, stale abort, queue success/failure.

---

## 9.2 execution_diagnosis_task (Inference Worker)
Purpose:
- Claims diagnosis job.
- Loads isolation forest model.
- Runs inference and risk scoring.
- Writes completion/failure path via diagnosis finalize APIs.

Branches:
1. HIGH risk -> /api/diagnosis/complete -> vehicle moves to DIAGNOSIS_COMPLETE + scheduling_required true.
2. LOW risk -> /api/diagnosis/complete_job_no_risk -> vehicle reset to IDLE.
3. Failure -> /api/diagnosis/fail or no-risk fail route.
4. Stale ownership -> mark stale diagnosis job.

---

## 9.3 scheduling_tasks
Purpose:
- Validates ASSIGNED_BY_SCHEDULING_AGENT ownership.
- Reuses existing booking if valid.
- Else obtains service slot and books tentative appointment.
- Updates workflow to SCHEDULING_COMPLETE and engagement_required true.

---

## 9.4 engagement_tasks
Purpose:
- Validates ASSIGNED_BY_ENGAGEMENT_AGENT ownership.
- Fetches latest prediction and booking.
- Extracts top 7-day issue indicators.
- Generates customer message via CrewAI LLM (or mock fallback).
- Sends email.
- Logs engagement.
- Updates workflow to ENGAGEMENT_COMPLETE.

Resilience:
- LLM init has fallback path to mock generation.

---

## 9.5 service_completion_tasks
Purpose:
- Validates ASSIGNED_BY_SERVICE_COMPLETION_AGENT ownership.
- Marks booking complete.
- Resets vehicle lifecycle state to IDLE baseline.
- Logs feedback completion event.

Outcome:
- Full lifecycle closure.

---

## 10. Vehicle Lifecycle State Machine

Primary journey:
1. Telemetry arrives -> vehicle_state refreshed -> IDLE.
2. Master decides diagnosis needed.
3. Master queues diagnosis task.
4. Diagnosis queue worker creates diagnosis job and sets DIAGNOSIS_PENDING.
5. Diagnosis agent dispatches execution worker.
6. Execution worker runs model:
   - high risk -> DIAGNOSIS_COMPLETE + scheduling_required true.
   - low risk -> reset to IDLE and close quickly.
7. Scheduling agent dispatches scheduling worker.
8. Scheduling worker creates booking and sets SCHEDULING_COMPLETE + engagement_required true.
9. Engagement agent dispatches engagement worker.
10. Engagement worker generates/sends message and sets ENGAGEMENT_COMPLETE.
11. Service completion agent dispatches completion worker.
12. Completion worker marks booking complete, logs feedback, resets to IDLE.

---

## 11. Edge Cases and Guard Rails

The system includes multiple safety controls:

1. Ownership checks before worker execution.
- Workers verify pipeline_status + celery_task_id match current task.

2. Lifecycle gates in every agent.
- Prevents duplicate/invalid transitions.

3. Telemetry ordering checks.
- last_processed_telemetry vs latest_feature_associated_telemetryID.

4. Timeout-based stale detection.
- Agents revoke old celery tasks and reset state.

5. Recovery reset baseline.
- Most stale/failure rollbacks reset pipeline/workflow/risk to known-safe defaults.

6. Multi-process sharding.
- Agents shard vehicle/job processing for throughput.

---

## 12. Observability and Activity Intelligence

The activity subsystem adds:
- unified event schema.
- persistence with indexed queries.
- websocket fanout.
- metrics overview with stage/risk/throughput counters.
- per-vehicle narrative summaries (technical/business/judge).

This is what enables the frontend to feel like a live control room instead of a static status page.

---

## 13. Frontend: What Has Been Implemented

Current frontend app folder:
- frontend

Implemented Phase C:
1. Global visual system
- dark control-room atmosphere
- custom accent palette by lifecycle stage
- typography and panel styling

2. Mission Control page
- live metrics cards
- lifecycle pressure map
- activity timeline feed
- websocket connection status

3. Vehicle Journey page
- per-vehicle timeline feed
- stage flow panel
- summary panel integrated with Phase B summary APIs

4. Data layer
- typed API clients for events, metrics, summary
- websocket + polling hybrid hook for robustness

5. Realtime behavior
- events stream into feed
- metrics periodically refreshed
- summary refresh actions supported

6. Queue + worker operational health
- queue depth is now wired from backend broker inspection
- worker heartbeat is now wired from Celery inspect stats
- dashboard health panel reflects live broker and worker state

7. Demo / Judge overlay
- mission-control dashboard includes a dedicated demo overlay
- spotlight vehicle picker plus judge summary narrative
- overlay pulls from summary endpoints and auto-regenerates when missing

---

## 14. What Frontend Changed in Backend/Agent Repository

To support frontend operation, backend/agent repository received major architecture upgrades:

1. Activity module and routes added.
- universal logging APIs
- websocket event stream
- summary endpoints
- mission-control metrics endpoint

2. Instrumentation wired into route transitions.
- telemetry ingestion
- diagnosis queue/finalize
- schedule updates
- service completion
- vehicle state transitions

3. Agent/worker instrumentation added.
- master agent decision events
- diagnosis worker lifecycle events

4. Runtime launcher/hardening added.
- one-command startup orchestration
- deterministic process startup and cleanup

These changes are what make frontend possible as an observability product.

---

## 15. Frontend Delivery Status (Phase C Complete)

Visual direction:
- black professional command-center interface
- high contrast, animated stage transitions
- narrative lifecycle framing instead of static tables

Phase C completed items (done):
1. Replay mode
- time-window event playback with speed controls.

2. Incident panel
- stale/failure and reset outcomes with traceability.

3. Queue/worker health panel
- live queue depth plus worker heartbeat integration.

4. Rich vehicle lane UX
- lane context chips plus lifecycle timing metadata.

5. Demo framing overlays
- judge mode narrative highlights tied to summary endpoints.

Post-Phase-C optional enhancements (not required for completion):
1. Additional visual refinement pass for demo-day brand tuning.
2. Deeper queue analytics (per-queue retry counters and worker latency histograms).

---

## 16. Operational Notes and Risks

1. Auth model is currently static header-key, not JWT.
2. Some route files duplicate diagnosis queue behavior; consolidation is recommended.
3. UEBA agent is not fully aligned with current backend API contracts.
4. Many resets are full-state baseline resets; this is safe but can be aggressive.
5. Several code paths use broad exception catches; observability helps but finer error classes would improve maintainability.

---

## 17. Why This Architecture Is Strong for Hackathon and Production Evolution

Strengths now:
- clear separation of decision and execution.
- async queue topology by stage.
- robust stale handling and lifecycle gates.
- audit-ready event stream and summaries.
- frontend-ready realtime data contracts.

Natural evolution path:
- replace static auth with JWT + service identities.
- formalize state machine transitions centrally.
- add idempotency keys for cross-service writes.
- add queue depth telemetry and autoscaling policy.
- harden UEBA and external notification channels.

---

## 18. Final One-Line Description You Can Reuse

AutoAI is a multi-agent, queue-driven autonomous vehicle service orchestration platform where agents make gated lifecycle decisions, Celery workers execute stage actions asynchronously, FastAPI provides a secure and observable control plane over MongoDB, and a realtime frontend visualizes the complete end-to-end journey from telemetry to lifecycle closure.
