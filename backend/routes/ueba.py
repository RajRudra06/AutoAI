from fastapi import APIRouter
from datetime import datetime
from backend.db.connection import db

router = APIRouter(prefix="/ueba", tags=["UEBA"])

@router.post("/log")
def log_ueba_event(payload: dict):
    payload["timestamp"] = datetime.utcnow()
    db.ueba_logs.insert_one(payload)
    return {"success": True}

@router.get("/logs")
def get_logs():
    logs = list(db.ueba_logs.find().sort("timestamp", -1))
    return {"data": logs}
