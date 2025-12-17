from fastapi import APIRouter
from backend.db.connection import db

router = APIRouter(prefix="/predictions", tags=["Predictions"])

@router.post("/")
def trigger_prediction(payload: dict):
    # TODO: call Diagnosis Agent later
    db.predictions.insert_one(payload)
    return {"success": True, "status": "prediction stored"}
