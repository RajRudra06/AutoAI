from fastapi import APIRouter
from datetime import datetime
from backend.db.connection import db

router = APIRouter(prefix="/telematics", tags=["Telemetry"])

@router.post("/data")
def receive_telemetry(payload: dict):

    payload["timestamp"] = datetime.utcnow()
    payload["status"] = "raw"  # not yet processed by any agent

    # 1️⃣ Store full telemetry history
    db.telemetry.insert_one(payload)

    vehicle_id = payload["vehicle_id"]

    # 2️⃣ Update per-vehicle shared state (single source of truth)
    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {
            "$set": {
                "vehicle_id": vehicle_id,
                "latest_telemetry": payload,
                "last_updated": datetime.utcnow(),
                "flags": {
                    "diagnosis_required": False,
                    "anomaly_detected": False
                }
            }
        },
        upsert=True
    )

    return {"success": True}
