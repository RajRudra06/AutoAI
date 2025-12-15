# agents/master_agent.py
import time
from datetime import datetime
from backend.db.connection import db
from helpers.logic.health_gate import needs_diagnosis

POLL_INTERVAL = 15  # seconds

def run_master():
    print("[MASTER] Agent started. Observing vehicle_state...")

    while True:
        vehicles = list(db.vehicle_state.find({}))

        for vehicle in vehicles:
            vehicle_id = vehicle["vehicle_id"]
            telemetry = vehicle.get("latest_telemetry", {})
            workflow = vehicle.get("workflow_state", {})
            flags = workflow.get("flags", {})

            # Skip if diagnosis already requested
            if flags.get("diagnosis_required"):
                continue

            should_trigger, reasons = needs_diagnosis(
                telemetry=telemetry,
                previous_telemetry=vehicle.get("previous_telemetry")
            )

            print(
                f"[MASTER][CHECK] {vehicle_id} | "
                f"stage={workflow.get('current_stage')} | "
                f"flags={flags}"
            )

            if not should_trigger:
                continue

            print(f"[MASTER] Diagnosis required for {vehicle_id}: {reasons}")

            # 1️⃣ Create diagnosis job
            db.diagnosis_jobs.insert_one({
                "vehicle_id": vehicle_id,
                "telemetry_snapshot": telemetry,
                "trigger_reasons": reasons,
                "status": "PENDING",
                "created_at": datetime.utcnow()
            })

            # 2️⃣ Update vehicle_state
            db.vehicle_state.update_one(
                {"vehicle_id": vehicle_id},
                {
                    "$set": {
                        "workflow_state.current_stage": "DIAGNOSIS_PENDING",
                        "workflow_state.flags.diagnosis_required": True,
                        "workflow_state.flags.high_risk_active": True,
                        "last_updated": datetime.utcnow()
                    }
                }
            )

            print(f"[MASTER][QUEUED] Diagnosis job created for {vehicle_id}")


        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_master()
