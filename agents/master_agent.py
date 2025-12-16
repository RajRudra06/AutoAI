# agents/master_agent.py
import time
from datetime import datetime, timezone

from backend.db.connection import db
from helpers.logic.health_gate import needs_diagnosis

POLL_INTERVAL = 15  # seconds


def run_master():
    print("[MASTER] Agent started. Observing vehicle_state...")

    while True:
        vehicles = list(db.vehicle_state.find({}))

        for vehicle in vehicles:
            vehicle_id = vehicle["vehicle_id"]

            latest = vehicle.get("latest_features")
            previous = vehicle.get("previous_features")

            workflow = vehicle.get("workflow_state", {})
            flags = workflow.get("flags", {})

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

            db.diagnosis_jobs.insert_one({
                "vehicle_id": vehicle_id,
                "features_snapshot": latest,
                "trigger_reasons": reasons,
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc)
            })

            db.vehicle_state.update_one(
                {"vehicle_id": vehicle_id},
                {
                    "$set": {
                        "workflow_state.current_stage": "DIAGNOSIS_PENDING",
                        "workflow_state.flags.diagnosis_required": True,
                        "last_updated": datetime.now(timezone.utc)
                    }
                }
            )

            print(
                f"[MASTER][QUEUED] {vehicle_id} → DIAGNOSIS_PENDING | reasons={reasons}"
            )

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_master()
