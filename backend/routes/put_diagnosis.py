from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone
from backend.db.connection import db

router = APIRouter(prefix="/diagnosis", tags=["Diagnosis"])

@router.post("/queue")
def queue_diagnosis(payload: dict, request: Request):
    agent_id = request.state.agent_id

    vehicle_id = payload["vehicle_id"]
    features = payload["features_snapshot"]
    reasons = payload.get("trigger_reasons", [])

    existing = db.vehicle_state.find_one({"vehicle_id": vehicle_id})
    if not existing:
        raise HTTPException(404, "Vehicle not found")

    # Create diagnosis job
    db.diagnosis_jobs.insert_one({
        "vehicle_id": vehicle_id,
        "features_snapshot": features,
        "trigger_reasons": reasons,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc),
        "requested_by": agent_id
    })

    # Update vehicle workflow
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

    return {"success": True, "vehicle_id": vehicle_id}
