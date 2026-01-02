# agents/ueba_agent.py
import time
import requests
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from agents.utils.agent_api_client import get, post

load_dotenv()

BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
GET_VEHICLES_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"
PUT_DIAGNOSIS_URL = f"{BASE_API_URL}/api/diagnosis/queue"
POLL_INTERVAL = 60  # slower is fine

NOW = lambda: datetime.now(timezone.utc)

def run_ueba_agent():
    print("[UEBA] Agent started")

    while True:
        resp = get(GET_VEHICLES_STATE_URL)
        vehicles = resp.json().get("vehicles", [])

        for v in vehicles:
            vehicle_id = v["vehicle_id"]
            flags = v["workflow_state"]["flags"]

            # -------- RULE 1: repeated diagnosis --------
            since = (NOW() - timedelta(days=7)).isoformat()
            jobs = requests.get(
                f"{API_BASE}/diagnosis_jobs?vehicle_id={vehicle_id}&since={since}",
            ).json().get("data", [])

            if len(jobs) > 3:
                escalate(vehicle_id, "REPEATED_FAILURE", len(jobs))
                continue

            # -------- RULE 2: ignored engagement --------
            if flags.get("engagement_required"):
                last_update = v.get("last_updated")
                if last_update and (NOW() - datetime.fromisoformat(last_update)).hours > 24:
                    escalate(vehicle_id, "IGNORED_ALERT", "engagement_pending")

        time.sleep(POLL_INTERVAL)


def escalate(vehicle_id, reason, details):
    print(f"[UEBA] Escalation → {vehicle_id} | {reason}")

    # Log UEBA event
    requests.post(
        f"{API_BASE}/ueba/log",
        headers=HEADERS,
        json={
            "vehicle_id": vehicle_id,
            "event": reason,
            "details": {"value": details}
        }
    )

    # Mark human escalation
    requests.post(
        f"{API_BASE}/vehicle_state/update",
        headers=HEADERS,
        json={
            "vehicle_id": vehicle_id,
            "workflow_state": {
                "flags": {
                    "human_escalation_required": True
                }
            }
        }
    )


if __name__ == "__main__":
    run_ueba_agent()
