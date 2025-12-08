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
