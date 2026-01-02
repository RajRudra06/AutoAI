from fastapi import APIRouter
from datetime import datetime, timezone
from backend.db.connection import db

router = APIRouter(prefix="/ueba", tags=["UEBA"])

@router.post("/log")
def log_ueba_event(payload: dict):
    db.ueba_logs.insert_one({
        "vehicle_id": payload["vehicle_id"],
        "event": payload["event"],
        "details": payload.get("details", {}),
        "created_at": datetime.now(timezone.utc)
    })
    return {"success": True}

@router.get("/logs")
def get_logs():
    logs = list(db.ueba_logs.find().sort("timestamp", -1))
    return {"data": logs}
