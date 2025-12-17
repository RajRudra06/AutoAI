from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone
from backend.db.connection import db

router = APIRouter(prefix="/service", tags=["Service"])

@router.post("/complete")
def complete_service(payload: dict, request: Request):
    agent_id = request.state.agent_id

    vehicle_id = payload["vehicle_id"]

    existing = db.vehicle_state.find_one({"vehicle_id": vehicle_id})
    if not existing:
        raise HTTPException(404, "Vehicle not found")

    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {
            "$set": {
                "workflow_state.current_stage": "IDLE",
                "workflow_state.flags": {
                    "diagnosis_required": False,
                    "scheduling_required": False,
                    "engagement_required": False
                },
                "risk_state": {
                    "high_risk_active": False,
                    "unresolved_issues": []
                },
                "last_service_completed_at": datetime.now(timezone.utc),
                "last_updated": datetime.now(timezone.utc)
            }
        }
    )

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "status": "RESET_TO_IDLE"
    }
