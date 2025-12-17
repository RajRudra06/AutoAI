from fastapi import APIRouter
from backend.db.connection import db
from datetime import datetime, timezone,timedelta
import random

router = APIRouter(prefix="/schedule", tags=["Scheduling"])


@router.post("/book")
def book_slot(payload: dict):
    payload.setdefault("created_at", datetime.now(timezone.utc))
    db.bookings.insert_one(payload)
    return {"success": True}


@router.get("/{vehicle_id}")
def get_booking(vehicle_id: str):
    appt = db.bookings.find_one(
        {"vehicle_id": vehicle_id},
        {"_id": 0}
    )
    return {"data": appt}

@router.get("/get_slot")
def generate_random_service_slot(days_ahead: int = 8) -> str:
  
    now = datetime.now(timezone.utc)

    # Random day within range
    day_offset = random.randint(1, days_ahead)
    service_date = now + timedelta(days=day_offset)

    # Random working hour
    hour = random.randint(9, 17)  # last slot starts at 5 PM
    minute = random.choice([0, 30])

    slot = service_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    return slot.isoformat()

    
@router.post("/update")
def update_vehicle_state(payload: dict):
    vehicle_id = payload["vehicle_id"]
    now = datetime.now(timezone.utc)

    update_doc = {"last_updated": now}

    if "workflow_state" in payload:
        update_doc["workflow_state"] = payload["workflow_state"]

    if "risk_state" in payload:
        update_doc["risk_state"] = payload["risk_state"]

    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": update_doc}
    )

    return {"success": True}
