from fastapi import APIRouter
from backend.db.connection import db

router = APIRouter(prefix="/predict", tags=["Prediction"])

@router.post("/")
def trigger_prediction(payload: dict):
    # TODO: call Diagnosis Agent later
    db.predictions.insert_one(payload)
    return {"success": True, "status": "prediction stored"}

@router.get("/latest/{vehicle_id}")
def latest_prediction(vehicle_id: str):
    pred = db.predictions.find_one({"vehicle_id": vehicle_id}, sort=[("timestamp",-1)])
    return {"data": pred}
