# AutoAI Phase Runbook

This file is the single source of truth for run and test commands.
It will be updated phase by phase as implementation progresses.

## Current Recommended Startup (One Command)

Run from project root:

./run_all.sh

What this does:
- Starts backend
- Starts collector, master, diagnosis, scheduling, engagement, and service completion agents
- Starts Celery workers for diagnosis, execution diagnosis, scheduling, engagement, and service completion queues
- Applies runtime env loading and TLS cert handling

## Stop Everything

In the same terminal where ./run_all.sh is running, press Ctrl+C.

## Quick Health Check

curl -sS http://127.0.0.1:8000/health

Expected response:
{"status":"ok"}

## Manual Fallback Commands (If Needed)

Use project-root absolute interpreter for consistency:

Backend:
PYTHONPATH=. ./AutoAI_ENV/bin/python -m uvicorn backend.main:app --port 8000

Collector:
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/collector_agent.py

Master:
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/master_agent.py

Diagnosis agent:
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/diagnosis_agent.py

Scheduling agent:
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/scheduling_agent.py

Engagement agent:
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/engagement_agent.py

Service completion agent:
PYTHONPATH=. ./AutoAI_ENV/bin/python agents/service_completion_agent.py

Diagnosis queue worker:
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q diagnosis_queue -n diagnosis_queue_worker@%h

Execution diagnosis queue worker:
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q execution_diagnosis_task_queue -n execution_diagnosis_queue_worker@%h

Scheduling queue worker:
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q scheduling_queue -n scheduling_queue_worker@%h

Engagement queue worker:
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker --loglevel=info --pool=threads --concurrency=4 --queues=engagement_queue -n engagement_queue_worker@%h

Service completion queue worker:
PYTHONPATH=. ./AutoAI_ENV/bin/python -m celery -A worker_tasks.celery_config worker -l info -Q service_completion_queue -n service_completion_queue_worker@%h

## Phase Command Log

## Phase A
- Added one-command launcher: ./run_all.sh
- Added launcher backend script: ./run_everything.py
- Added Phase A API test script: ./phase_a_e2e_test.sh
- Added websocket e2e validation command (see below)

### Phase A Validation Commands

HTTP endpoint suite:

./phase_a_e2e_test.sh

Realtime websocket check:

./AutoAI_ENV/bin/python - <<'PY'
import asyncio
import json
import requests
import websockets

BASE='http://127.0.0.1:8000'
WS='ws://127.0.0.1:8000/api/activity/ws'

async def main():
	async with websockets.connect(WS, additional_headers={
		'X-AGENT-ID': 'agent_001',
		'X-API-KEY': 'secret_key_001',
	}) as ws:
		payload={
			'vehicle_id':'V_PHASE_A_WS',
			'source_type':'api',
			'source_name':'phase_a_ws_test',
			'stage_from':'IDLE',
			'stage_to':'DIAGNOSIS_PENDING',
			'action':'phase_a_ws_event',
			'status':'success',
			'summary':'Phase A websocket e2e event',
			'details':{'suite':'phase_a','step':'ws'}
		}
		r=requests.post(
			f"{BASE}/api/activity/log",
			headers={'X-AGENT-ID':'agent_001','X-API-KEY':'secret_key_001'},
			json=payload,
			timeout=5,
		)
		print('POST status:', r.status_code)
		msg=await asyncio.wait_for(ws.recv(), timeout=8)
		data=json.loads(msg)
		print('WS source_name:', data.get('source_name'))
		print('WS action:', data.get('action'))
		print('WS vehicle_id:', data.get('vehicle_id'))

asyncio.run(main())
PY

## Phase B
- Added summary endpoints:
	- POST /api/activity/summary/{vehicle_id}
	- GET /api/activity/summary/{vehicle_id}
- Expanded `GET /api/activity/metrics/overview` with fleet/risk/throughput counters.
- Added backend instrumentation emits across routes, master agent, and diagnosis worker.

### Phase B Validation Commands

Generate summary for one vehicle timeline:

curl -sS -H 'X-AGENT-ID: agent_001' -H 'X-API-KEY: secret_key_001' -X POST http://127.0.0.1:8000/api/activity/summary/V_PHASE_A

Fetch latest summary:

curl -sS -H 'X-AGENT-ID: agent_001' -H 'X-API-KEY: secret_key_001' http://127.0.0.1:8000/api/activity/summary/V_PHASE_A

Fetch enhanced mission-control metrics:

curl -sS -H 'X-AGENT-ID: agent_001' -H 'X-API-KEY: secret_key_001' 'http://127.0.0.1:8000/api/activity/metrics/overview?window_events=100'

## Phase C
- Pending

## Phase D
- Pending

## Phase E
- Pending
