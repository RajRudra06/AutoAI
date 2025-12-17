from fastapi import APIRouter, HTTPException, Request
from backend.db.connection import db

router = APIRouter(prefix="/vehicles", tags=["Vehicle State"])

@router.get("/state")
def get_all_vehicle_states(request: Request):
    agent_id = request.state.agent_id  # future use

    vehicles = list(
        db.vehicle_state.find({}, {"_id": 0})
    )
    return {"vehicles": vehicles}

@router.get("/state/{vehicle_id}")
def get_vehicle_state(vehicle_id: str, request: Request):
    agent_id = request.state.agent_id  

    vehicle = db.vehicle_state.find_one(
        {"vehicle_id": vehicle_id},
        {"_id": 0}
    )

    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle {vehicle_id} not found"
        )

    return vehicle

@router.post("/update")
def update_vehicle_state(payload: dict):
    vehicle_id = payload["vehicle_id"]
    workflow_state = payload.get("workflow_state")

    update_doc = {}
    if workflow_state:
        update_doc["workflow_state"] = workflow_state

    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": update_doc}
    )

    return {"success": True}
