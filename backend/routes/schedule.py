from fastapi import APIRouter
from backend.db.connection import db

router = APIRouter(prefix="/schedule", tags=["Scheduling"])

@router.post("/book")
def book_slot(payload: dict):
    db.bookings.update_one(
        {"vehicle_id": payload["vehicle_id"]},
        {"$set": payload},
        upsert=True
    )
    return {"success": True}

@router.get("/{vehicle_id}")
def get_booking(vehicle_id: str):
    appt = db.bookings.find_one({"vehicle_id": vehicle_id})
    return {"data": appt}
