from fastapi import APIRouter
from backend.db.connection import db

router = APIRouter(prefix="/predictions", tags=["Predictions"])

@router.post("/")
def trigger_prediction(payload: dict):
    # TODO: call Diagnosis Agent later
    db.predictions.insert_one(payload)
    return {"success": True, "status": "prediction stored"}

@router.get("/{vehicle_id}")
def get_latest_prediction(vehicle_id: str):
    pred = db.predictions.find_one(
        {"vehicle_id": vehicle_id},
        sort=[("created_at", -1)],
        projection={"_id": 0}
    )
    return {"data": pred}