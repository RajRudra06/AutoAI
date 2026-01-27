from fastapi import APIRouter
from datetime import datetime, timezone
from backend.db.connection import db

router = APIRouter(prefix="/telematics", tags=["Telemetry"])

@router.post("/data")
def receive_telemetry(payload: dict):
  
    vehicle_id = payload["vehicle_id"]
    features = payload["features"]

    now = datetime.now(timezone.utc)

    latest_telemetry_ID=payload.get("timestamp", now)
    db.telemetry.insert_one({
        "vehicle_id": vehicle_id,
        "telemetryID": latest_telemetry_ID,
        "features": features,
        "status":"new"
    })

    existing_state = db.vehicle_state.find_one(
        {"vehicle_id": vehicle_id},
        {"latest_features": 1}
    )

    previous_features = (
        existing_state["latest_features"]
        if existing_state and "latest_features" in existing_state
        else None
    )

    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {
            "$set": {
                "vehicle_id": vehicle_id,
                "latest_features": features,
                "previous_features": previous_features,
                "latest_feature_associated_telemetryID":latest_telemetry_ID,
                "last_updated": now,
                "last_processed_telemetry":datetime(1970, 1, 1, tzinfo=timezone.utc)
            },
            "$setOnInsert": {
                # Initialized once, never overwritten here
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
            }
        },
        upsert=True
    )

    return {"success": True}
