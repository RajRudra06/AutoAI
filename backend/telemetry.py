from fastapi import APIRouter
from datetime import datetime
from backend.db import db

router = APIRouter(prefix="/telematics", tags=["Telemetry"])

@router.post("/data")
def receive_data(payload: dict):
    payload["timestamp"] = datetime.utcnow()
    db.telemetry.insert_one(payload)
    return {"success": True, "message": "Telemetry stored"}
