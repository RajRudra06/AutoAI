from fastapi import APIRouter
from datetime import datetime
from backend.db.connection import db

router = APIRouter(prefix="/telematics", tags=["Telemetry"])

MAX_RECORDS = 15

@router.post("/data")
def receive_telemetry(payload: dict):
    payload["timestamp"] = datetime.utcnow()
    db.telemetry.insert_one(payload)

    # Cleanup: keep only the latest MAX_RECORDS
    count = db.telemetry.count_documents({})
    if count > MAX_RECORDS:
        # delete oldest documents
        to_delete = count - MAX_RECORDS
        db.telemetry.delete_many(
            {}, 
            sort=[("timestamp", 1)],
            limit=to_delete
        )

    return {"success": True}
