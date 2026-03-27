#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8000"

echo "[1/5] health"
curl -sS "$BASE/health"
echo

echo "[2/5] POST /api/activity/log"
curl -sS -X POST "$BASE/api/activity/log" \
  -H 'Content-Type: application/json' \
  -H 'X-AGENT-ID: agent_001' \
  -H 'X-API-KEY: secret_key_001' \
  -d '{"vehicle_id":"V_PHASE_A","source_type":"api","source_name":"phase_a_e2e_test","stage_from":"IDLE","stage_to":"DIAGNOSIS_PENDING","action":"phase_a_e2e_event","status":"success","summary":"Phase A e2e manual event","details":{"suite":"phase_a","step":"post"}}'
echo

echo "[3/5] GET /api/activity/events"
curl -sS "$BASE/api/activity/events?source_name=phase_a_e2e_test&limit=3" \
  -H 'X-AGENT-ID: agent_001' \
  -H 'X-API-KEY: secret_key_001'
echo

echo "[4/5] GET /api/activity/vehicle/V_PHASE_A"
curl -sS "$BASE/api/activity/vehicle/V_PHASE_A?limit=3" \
  -H 'X-AGENT-ID: agent_001' \
  -H 'X-API-KEY: secret_key_001'
echo

echo "[5/5] GET /api/activity/metrics/overview"
curl -sS "$BASE/api/activity/metrics/overview?window_events=300" \
  -H 'X-AGENT-ID: agent_001' \
  -H 'X-API-KEY: secret_key_001'
echo
