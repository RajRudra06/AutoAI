from fastapi import APIRouter
from backend.db.connection import db

router = APIRouter(prefix="/feedback", tags=["Feedback"])

@router.post("/")
def submit_feedback(payload: dict):
    db.feedback.insert_one(payload)
    return {"success": True}

@router.get("/{vehicle_id}")
def get_feedback(vehicle_id: str):
    fb = db.feedback.find_one({"vehicle_id": vehicle_id})
    return {"data": fb}

@router.post("/log")
def log_feedback(payload: dict):
    """
    Logs final service feedback / lifecycle closure events.
    Used by Service Completion or Engagement agents.
    """

    doc = {
        "vehicle_id": payload["vehicle_id"],
        "event": payload.get("event", "SERVICE_COMPLETED"),
        "details": payload.get("details", {}),
        "created_at": payload.get("created_at") or datetime.now(timezone.utc)
    }

    db.feedback.insert_one(doc)
    return {"success": True}
