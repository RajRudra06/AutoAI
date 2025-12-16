from fastapi import APIRouter, Request
from backend.db.connection import db

router = APIRouter(prefix="/vehicle-state", tags=["Vehicle State"])

@router.get("/")
def get_vehicle_states(request: Request):
    agent_id = request.state.agent_id  # future use

    vehicles = list(db.vehicle_state.find({}, {"_id": 0}))
    return vehicles

