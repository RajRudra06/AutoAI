from fastapi import APIRouter, HTTPException, Request
from backend.db.connection import db
from datetime import datetime,timezone

router = APIRouter(prefix="/vehicles", tags=["Vehicle State"])

@router.get("/state")
def get_all_vehicle_states(request: Request):
    agent_id = request.state.agent_id  

    vehicles = list(
        db.vehicle_state.find({}, {"_id": 0})
    )
    
    for vehicle in vehicles:
        datetime_fields = [
            'last_updated',
            'last_processed_telemetry', 
            'temp_last_processed_telemetry',
            'latest_feature_associated_telemetryID'
        ]
        
        for field in datetime_fields:
            if field in vehicle and isinstance(vehicle[field], datetime):
                if vehicle[field].tzinfo is None:
                    vehicle[field] = vehicle[field].replace(tzinfo=timezone.utc)
                vehicle[field] = vehicle[field].isoformat()
        
        if 'pipeline_associated' in vehicle and vehicle['pipeline_associated']:
            pa = vehicle['pipeline_associated'].get('pipeline_assigned_at')
            if pa and isinstance(pa, datetime):
                if pa.tzinfo is None:
                    pa = pa.replace(tzinfo=timezone.utc)
                vehicle['pipeline_associated']['pipeline_assigned_at'] = pa.isoformat()
    
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
    risk_state = payload.get("risk_state")
    temp_last_processed_telemetry = payload.get("temp_last_processed_telemetry")
    last_processed_telemetry=payload.get("last_processed_telemetry")
    pipeline_associated=payload.get("pipeline_associated")

    update_doc = {}

    if workflow_state is not None:
        update_doc["workflow_state"] = workflow_state
        update_doc["risk_state"] = risk_state

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
    if pipeline_associated is not None:
        if "pipeline_status" in pipeline_associated:
            update_doc["pipeline_associated.pipeline_status"] = (
                pipeline_associated["pipeline_status"]
            )

        if "pipeline_assigned_at" in pipeline_associated:
            ts = pipeline_associated["pipeline_assigned_at"]
            update_doc["pipeline_associated.pipeline_assigned_at"] = (
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if isinstance(ts, str)
                else ts
            )
        if "celery_task_id" in pipeline_associated:
            update_doc["pipeline_associated.celery_task_id"]=pipeline_associated["celery_task_id"]
            
    if risk_state is not None:
        update_doc["risk_state"] = risk_state

    dot_celery_id = payload.get("pipeline_associated.celery_task_id")
    if dot_celery_id is not None or "pipeline_associated.celery_task_id" in payload:
        update_doc["pipeline_associated.celery_task_id"] = dot_celery_id
            
    if update_doc:
        db.vehicle_state.update_one(
            {"vehicle_id": vehicle_id},
            {"$set": update_doc}
        )

    return {"success": True}
