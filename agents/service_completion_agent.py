import time
import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timezone
from agents.utils.agent_api_client import get, post

load_dotenv()

BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
GET_VEHICLES_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"
GET_VEHICLE_SCHEDULE = f"{BASE_API_URL}/api/schedule"
VEHICLE_SCHEDULE_UPDATE = f"{BASE_API_URL}/api/schedule/update"
UPDATE_VEHICLE_STATE = f"{BASE_API_URL}/api/vehicles/update"
FEEDBACK_LOG_URL=f"{BASE_API_URL}/api/feedback/log"

POLL_INTERVAL=20

def run_service_completion_agent():
    print("[SERVICE] Agent started. Waiting for service completion...")

    while True:
        resp = get(GET_VEHICLES_STATE_URL)
        vehicles = resp.json().get("vehicles", [])

        for v in vehicles:
            vehicle_id = v["vehicle_id"]
            stage = v["workflow_state"]["current_stage"]

            if stage != "ENGAGEMENT_COMPLETE":
                continue

            booking = get(
                f"{GET_VEHICLE_SCHEDULE}/{vehicle_id}",
            ).json().get("data")

            if not booking or booking.get("status") == "COMPLETED":
                continue

            print(f"[SERVICE] Completing service for {vehicle_id}")

            post(
                f"{VEHICLE_SCHEDULE_UPDATE}",
                json={
                    "vehicle_id": vehicle_id,
                    "status": "COMPLETED",
                    "completed_at": datetime.now(timezone.utc).isoformat()
                },
            )

            post(
                f"{UPDATE_VEHICLE_STATE}",
                json={
                    "vehicle_id": vehicle_id,
                    "workflow_state": {
                        "current_stage": "IDLE",
                        "flags": {
                            "diagnosis_required": False,
                            "scheduling_required": False,
                            "engagement_required": False
                        }
                    },
                    "risk_state": {
                        "high_risk_active": False,
                        "unresolved_issues": []
                    }
                },
            )

            # 3️⃣ Log feedback
            post(
                FEEDBACK_LOG_URL,
                json={
                    "vehicle_id": vehicle_id,
                    "message": "Service completed successfully",
                    "created_at": datetime.now(timezone.utc).isoformat()
                },
            )

            print(f"[SERVICE] Lifecycle closed for {vehicle_id}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_service_completion_agent()
