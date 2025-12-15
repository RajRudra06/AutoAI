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

            latest = vehicle.get("latest_telemetry")
            previous = vehicle.get("previous_telemetry")

            workflow = vehicle.get("workflow_state", {})
            flags = workflow.get("flags", {})

            # ----------------------------
            # 1️⃣ Skip if diagnosis already requested
            # ----------------------------
            if flags.get("diagnosis_required"):
                continue

            # ----------------------------
            # 2️⃣ Health gate (cheap pre-filter)
            # ----------------------------
            should_trigger, reasons = needs_diagnosis(
                telemetry=latest,
                previous_telemetry=previous
            )

            print(
                f"[MASTER][CHECK] {vehicle_id} | "
                f"stage={workflow.get('current_stage')} | "
                f"flags={flags}"
            )

            if not should_trigger:
                continue

            # ----------------------------
            # 3️⃣ Create diagnosis job
            # ----------------------------
            db.diagnosis_jobs.insert_one({
                "vehicle_id": vehicle_id,
                "telemetry_snapshot": latest,
                "trigger_reasons": reasons,
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc)
            })

            # ----------------------------
            # 4️⃣ Advance WORKFLOW ONLY
            # ----------------------------
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
