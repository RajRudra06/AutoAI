# agents/master_agent.py

import time
import os
from dotenv import load_dotenv
from agents.utils.agent_api_client import get, post
from helpers.logic.health_gate import needs_diagnosis

load_dotenv()

POLL_INTERVAL = 15  # seconds
BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
GET_VEHICLES_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"
PUT_DIAGNOSIS_URL = f"{BASE_API_URL}/api/diagnosis/queue"

def run_master():
    print("[MASTER] Agent started. Observing vehicle_state...")

    while True:
        try:
            # 🔽 CHANGED: new endpoint + response shape
            resp = get(GET_VEHICLES_STATE_URL)
            vehicles = resp.json().get("vehicles", [])

        except Exception as e:
            print("[MASTER][ERROR] Failed to fetch vehicle state:", e)
            time.sleep(POLL_INTERVAL)
            continue

        for vehicle in vehicles:
            vehicle_id = vehicle["vehicle_id"]

            workflow = vehicle.get("workflow_state", {})
            risk_state = vehicle.get("risk_state", {})

            # ================================
            # 🚫 LIFECYCLE GATE
            # ================================
            if workflow.get("current_stage") in {
                "DIAGNOSIS_PENDING",
                "DIAGNOSIS_COMPLETE",
                "SCHEDULING",
                "IN_SERVICE"
            }:
                continue

            if risk_state.get("high_risk_active"):
                continue

            flags = workflow.get("flags", {})
            latest = vehicle.get("latest_features")
            previous = vehicle.get("previous_features")

            if flags.get("diagnosis_required"):
                continue

            should_trigger, reasons = needs_diagnosis(
                telemetry=latest,
                previous_telemetry=previous
            )

            print(
                f"[MASTER][CHECK] {vehicle_id} | "
                f"trigger={should_trigger} | "
                f"reasons={reasons} | "
                f"stage={workflow.get('current_stage')} | "
                f"flags={flags}"
            )

            if not should_trigger:
                continue

            try:
                post(
                    PUT_DIAGNOSIS_URL,
                    json={
                        "vehicle_id": vehicle_id,
                        "features_snapshot": latest,
                        "trigger_reasons": reasons
                    }
                )
                print(f"[MASTER][QUEUED] {vehicle_id} → DIAGNOSIS_PENDING")

            except Exception as e:
                print(f"[MASTER][ERROR] Failed to queue {vehicle_id}: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_master()
