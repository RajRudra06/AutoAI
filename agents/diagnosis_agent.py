# agents/diagnosis_agent.py
import time
from datetime import datetime, timezone
from backend.db.connection import db

POLL_INTERVAL = 10  # seconds


def diagnose(telemetry: dict) -> dict:

    issues = []

    if telemetry.get("engine_temp", 0) > 110:
        issues.append({
            "component": "engine",
            "issue": "overheating",
            "severity": "HIGH"
        })

    if telemetry.get("brake_wear", 0) > 0.8:
        issues.append({
            "component": "brakes",
            "issue": "excessive wear",
            "severity": "HIGH"
        })

    if telemetry.get("battery_health", 100) < 30:
        issues.append({
            "component": "battery",
            "issue": "degrading",
            "severity": "MEDIUM"
        })

    return {
        "issues": issues,
        "risk_level": "HIGH" if issues else "LOW"
    }


def run_diagnosis():
    print("[DIAGNOSIS] Agent started. Waiting for jobs...")

    while True:
        jobs = list(db.diagnosis_jobs.find({"status": "PENDING"}))

        for job in jobs:
            vehicle_id = job["vehicle_id"]
            telemetry = job["telemetry_snapshot"]

            print(f"[DIAGNOSIS] Processing job for {vehicle_id}")

            result = diagnose(telemetry)

            # 1️⃣ Store prediction output
            db.predictions.insert_one({
                "vehicle_id": vehicle_id,
                "diagnosis": result,
                "telemetry_snapshot": telemetry,
                "created_at": datetime.now(timezone.utc)
            })

            # 2️⃣ Update vehicle_state (IMPORTANT PART)
            db.vehicle_state.update_one(
                {"vehicle_id": vehicle_id},
                {
                    "$set": {
                        # Workflow progression
                        "workflow_state.current_stage": "DIAGNOSIS_COMPLETE",
                        "workflow_state.flags.diagnosis_required": False,
                        "workflow_state.flags.scheduling_required": True,

                        # Risk reality (persists until maintenance)
                        "risk_state.high_risk_active": True,
                        "risk_state.unresolved_issues": [
                            issue["component"] for issue in result["issues"]
                        ],

                        "last_updated": datetime.now(timezone.utc)
                    }
                }
            )

            # 3️⃣ Close diagnosis job
            db.diagnosis_jobs.update_one(
                {"_id": job["_id"]},
                {
                    "$set": {
                        "status": "COMPLETED",
                        "completed_at": datetime.now(timezone.utc)
                    }
                }
            )

            print(f"[DIAGNOSIS] Completed job for {vehicle_id}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_diagnosis()
