from fastapi import APIRouter, HTTPException, Request
from backend.db.connection import db
from datetime import datetime,timezone

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

# @router.post("/update")
# def update_vehicle_state(payload: dict):
#     vehicle_id = payload["vehicle_id"]
#     workflow_state = payload.get("workflow_state")
#     risk_state=payload.get("risk_state")

#     update_doc = {}
#     if workflow_state:
#         update_doc["workflow_state"] = workflow_state
#         update_doc["risk_state"]=risk_state

#     db.vehicle_state.update_one(
#         {"vehicle_id": vehicle_id},
#         {"$set": update_doc}
#     )

#     return {"success": True}

@router.post("/update")
def update_vehicle_state(payload: dict):
    vehicle_id = payload["vehicle_id"]

    workflow_state = payload.get("workflow_state")
    risk_state = payload.get("risk_state")
    temp_last_processed_telemetry = payload.get("temp_last_processed_telemetry")
    last_processed_telemetry=payload.get("last_processed_telemetry")

    update_doc = {}

    # ✅ EXISTING BEHAVIOR (unchanged)
    if workflow_state is not None:
        update_doc["workflow_state"] = workflow_state
        update_doc["risk_state"] = risk_state

    # ✅ NEW BEHAVIOR (added)
    if temp_last_processed_telemetry is not None:
        update_doc["temp_last_processed_telemetry"] = (
            datetime.fromisoformat(temp_last_processed_telemetry)
            if isinstance(temp_last_processed_telemetry, str)
            else temp_last_processed_telemetry
        )

    if last_processed_telemetry is not None:
        update_doc["last_processed_telemetry"]=(
            datetime.fromisoformat(last_processed_telemetry)
            if isinstance(last_processed_telemetry,str)
            else last_processed_telemetry
        )

    # ✅ Prevent no-op updates
    if update_doc:
        db.vehicle_state.update_one(
            {"vehicle_id": vehicle_id},
            {"$set": update_doc}
        )

    return {"success": True}
