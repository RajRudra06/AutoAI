import time
import requests
from datetime import datetime, timezone
from agents.utils.agent_api_client import get, post
from helpers.logic.slot_generator import generate_random_service_slot
from dotenv import load_dotenv
import os

load_dotenv()

BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
GET_VEHICLES_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"
GET_BOOKING_FOR_VEHICLE_URL = f"{BASE_API_URL}/api/schedule"
BOOK_SCHEDULE_URL = f"{BASE_API_URL}/api/schedule/book"
UPDATE_STATE_URL = f"{BASE_API_URL}/api/schedule/update"
GET_SERVICE_SLOT = f"{BASE_API_URL}/api/schedule/get_slot"

POLL_INTERVAL = 15  # seconds

def run_scheduler():
    print("[SCHEDULER] Agent started. Monitoring scheduling_required flags...")

    while True:

        resp = get(GET_VEHICLES_STATE_URL)
        vehicles = resp.json().get("vehicles", [])

        for vehicle in vehicles:
            vehicle_id = vehicle["vehicle_id"]
            workflow = vehicle.get("workflow_state", {})
            flags = workflow.get("flags", {})

            if workflow.get("current_stage") == "SCHEDULING_COMPLETE":
                continue

            if not flags.get("scheduling_required"):
                continue

            booking_resp = get(
                f"{GET_BOOKING_FOR_VEHICLE_URL}/{vehicle_id}"
            )

            if booking_resp.status_code == 200 and booking_resp.headers.get("content-type", "").startswith("application/json"):
                data = booking_resp.json()
                if data.get("data"):
                    print(f"[SCHEDULER] Booking already exists for {vehicle_id}, skipping")
                    continue

            print(f"[SCHEDULER] Creating tentative booking for {vehicle_id}")

            slot_resp = get(GET_SERVICE_SLOT)
            slot_to_book = slot_resp.text.strip('"')


            booking_payload = {
                "vehicle_id": vehicle_id,
                "slot": slot_to_book, 
                "center_id": "SC-01",
                "status": "TENTATIVE",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            post(
                f"{BOOK_SCHEDULE_URL}",
                json=booking_payload,
            )

            post(
                UPDATE_STATE_URL,
                json={
                    "vehicle_id": vehicle_id,
                    "workflow_state": {
                        "current_stage": "SCHEDULING_COMPLETE",
                        "flags": {
                            "scheduling_required": False,
                            "engagement_required": True
                        }
                    }
                },
            )

            print(f"[SCHEDULER] Scheduling complete → Engagement required for {vehicle_id}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_scheduler()
