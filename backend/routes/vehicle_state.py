from fastapi import APIRouter, HTTPException, Request
from backend.db.connection import db
from datetime import datetime,timezone
from backend.activity.helpers import emit_activity_event
from pydantic import BaseModel, Field
import random
import re

router = APIRouter(prefix="/vehicles", tags=["Vehicle State"])


class VehicleRegistrationPayload(BaseModel):
    owner_id: str = Field(min_length=1)
    owner_name: str | None = None
    owner_email: str | None = None
    vehicle_name: str = Field(min_length=1)
    company: str = Field(min_length=1)
    vehicle_type: str = Field(min_length=1)
    model: str = Field(min_length=1)
    year: int | None = None


def _slugify(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def _create_vehicle_id(vehicle_name: str) -> str:
    base = _slugify(vehicle_name)[:18] or "VEHICLE"
    candidate = f"V_{base}"
    if not db.vehicle_state.find_one({"vehicle_id": candidate}, {"_id": 1}):
        return candidate

    suffix = random.randint(100, 999)
    while db.vehicle_state.find_one({"vehicle_id": f"{candidate}_{suffix}"}, {"_id": 1}):
        suffix = random.randint(100, 999)

    return f"{candidate}_{suffix}"


def _simulated_features(vehicle_type: str) -> dict:
    type_key = vehicle_type.lower()
    base_speed = 54 if type_key in {"truck", "suv"} else 62
    return {
        "speed_kmph": round(random.uniform(base_speed - 8, base_speed + 9), 1),
        "battery_percent": round(random.uniform(44, 95), 1),
        "engine_temp_c": round(random.uniform(72, 104), 1),
        "oil_health_percent": round(random.uniform(58, 99), 1),
        "tire_pressure_psi": round(random.uniform(30, 36), 1),
        "odometer_km": random.randint(2_000, 210_000),
        "engine_rpm": random.randint(1800, 2500),
        "fuel_level_percent": round(random.uniform(60, 90), 1),
        "coolant_pressure_psi": round(random.uniform(15, 20), 1),
        "intake_air_temp_c": round(random.uniform(35, 45), 1),
        "throttle_pos_percent": round(random.uniform(10, 30), 1),
        "brake_pad_wear_percent": round(random.uniform(80, 95), 1),
    }


def _mutate_simulated_features(current: dict) -> dict:
    latest = dict(current or {})
    latest["speed_kmph"] = round(max(0, min(220, float(latest.get("speed_kmph", 55)) + random.uniform(-4, 5))), 1)
    latest["battery_percent"] = round(max(0, min(100, float(latest.get("battery_percent", 75)) - random.uniform(0.01, 0.05))), 2)
    latest["engine_temp_c"] = round(max(30, min(130, float(latest.get("engine_temp_c", 84)) + random.uniform(-1.5, 2.0))), 1)
    latest["oil_health_percent"] = round(max(0, min(100, float(latest.get("oil_health_percent", 80)) - random.uniform(0.01, 0.05))), 2)
    latest["tire_pressure_psi"] = round(max(15, min(50, float(latest.get("tire_pressure_psi", 33)) + random.uniform(-0.2, 0.2))), 1)
    latest["engine_rpm"] = round(max(700, min(7500, float(latest.get("engine_rpm", 2000)) + random.uniform(-150, 150))), 0)
    latest["fuel_level_percent"] = round(max(0, min(100, float(latest.get("fuel_level_percent", 75)) - random.uniform(0.01, 0.05))), 2)
    latest["coolant_pressure_psi"] = round(max(0, min(40, float(latest.get("coolant_pressure_psi", 17)) + random.uniform(-0.2, 0.2))), 1)
    latest["intake_air_temp_c"] = round(max(10, min(90, float(latest.get("intake_air_temp_c", 40)) + random.uniform(-0.3, 0.3))), 1)
    latest["throttle_pos_percent"] = round(max(0, min(100, float(latest.get("throttle_pos_percent", 20)) + random.uniform(-4, 4))), 1)
    latest["brake_pad_wear_percent"] = round(max(0, min(100, float(latest.get("brake_pad_wear_percent", 85)) - random.uniform(0.001, 0.005))), 2)
    # Extra sensors for RawDataGenerator compatibility
    latest["oil_pressure_psi"] = round(max(0, min(100, float(latest.get("oil_pressure_psi", 40)) + random.uniform(-0.5, 0.5))), 1)
    latest["brake_pad_mm"] = round(max(0, min(15, float(latest.get("brake_pad_mm", 10)) - random.uniform(0.01, 0.03))), 2)
    latest["vibration_level"] = round(max(0, min(5, float(latest.get("vibration_level", 0.1)) + random.uniform(-0.01, 0.02))), 3)
    latest["transmission_temp_c"] = round(max(30, min(130, float(latest.get("transmission_temp_c", 75)) + random.uniform(-0.5, 0.5))), 1)
    latest["coolant_temp_c"] = round(max(30, min(130, float(latest.get("coolant_temp_c", 80)) + random.uniform(-0.5, 0.5))), 1)
    return latest


def _refresh_simulated_vehicle(vehicle: dict) -> dict:
    if not vehicle.get("simulated_telemetry"):
        return vehicle

    last_updated = vehicle.get("last_updated")
    now = datetime.now(timezone.utc)

    if not isinstance(last_updated, datetime):
        return vehicle

    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    if (now - last_updated).total_seconds() < 12:
        return vehicle

    updated_features = _mutate_simulated_features(vehicle.get("latest_features") or {})
    unresolved = list(vehicle.get("risk_state", {}).get("unresolved_issues") or [])

    if updated_features.get("engine_temp_c", 0) > 110 and "Engine temperature is above safe range" not in unresolved:
        unresolved.append("Engine temperature is above safe range")
    if updated_features.get("battery_percent", 100) < 18 and "Battery charge is critically low" not in unresolved:
        unresolved.append("Battery charge is critically low")

    high_risk = bool(unresolved)
    update_doc = {
        "latest_features": updated_features,
        "risk_state": {
            "high_risk_active": high_risk,
            "unresolved_issues": unresolved,
        },
        "last_updated": now,
    }

    db.vehicle_state.update_one({"vehicle_id": vehicle["vehicle_id"]}, {"$set": update_doc})
    vehicle.update(update_doc)
    return vehicle


@router.post("/register")
def register_vehicle(payload: VehicleRegistrationPayload):
    vehicle_id = _create_vehicle_id(payload.vehicle_name)
    now = datetime.now(timezone.utc)

    vehicle_doc = {
        "vehicle_id": vehicle_id,
        "owner_id": payload.owner_id,
        "owner_name": payload.owner_name,
        "owner_email": payload.owner_email,
        "vehicle_profile": {
            "name": payload.vehicle_name,
            "company": payload.company,
            "type": payload.vehicle_type,
            "model": payload.model,
            "year": payload.year,
        },
        "latest_features": _simulated_features(payload.vehicle_type),
        "workflow_state": {
            "current_stage": "IDLE",
            "flags": {
                "diagnosis_required": False,
                "scheduling_required": False,
                "engagement_required": False,
            },
        },
        "risk_state": {
            "high_risk_active": False,
            "unresolved_issues": [],
        },
        "pipeline_associated": {
            "pipeline_status": "INITIALIZED",
            "pipeline_assigned_at": now,
            "celery_task_id": None,
        },
        "simulated_telemetry": True,
        "last_updated": now,
    }

    db.vehicle_state.insert_one(vehicle_doc)

    emit_activity_event(
        vehicle_id=vehicle_id,
        source_type="api",
        source_name="vehicle_register_route",
        stage_from="IDLE",
        stage_to="IDLE",
        action="vehicle_registered",
        status="success",
        summary="Vehicle was registered and linked to user account.",
        details={
            "owner_id": payload.owner_id,
            "company": payload.company,
            "vehicle_type": payload.vehicle_type,
            "model": payload.model,
        },
    )

    # Remove the ObjectId inserted by pymongo before returning
    if "_id" in vehicle_doc:
        del vehicle_doc["_id"]

    return {"success": True, "vehicle_id": vehicle_id, "vehicle": vehicle_doc}

@router.get("/state")
def get_all_vehicle_states(request: Request, owner_id: str | None = None):
    agent_id = request.state.agent_id  

    filters = {"owner_id": owner_id} if owner_id else {}
    vehicles = list(
        db.vehicle_state.find(filters, {"_id": 0})
    )
    
    for vehicle in vehicles:
        vehicle = _refresh_simulated_vehicle(vehicle)
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
    existing = db.vehicle_state.find_one(
        {"vehicle_id": vehicle_id},
        {"workflow_state.current_stage": 1, "pipeline_associated.pipeline_status": 1, "_id": 0},
    ) or {}
    previous_stage = (
        existing.get("workflow_state", {})
        .get("current_stage")
    )

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

    next_stage = (workflow_state or {}).get("current_stage") if workflow_state is not None else None
    if next_stage and next_stage != previous_stage:
        emit_activity_event(
            vehicle_id=vehicle_id,
            source_type="api",
            source_name="vehicle_state_route",
            stage_from=previous_stage,
            stage_to=next_stage,
            action="vehicle_state_transition",
            status="success",
            summary="Vehicle workflow stage changed via state update API.",
            details={
                "pipeline_status": (pipeline_associated or {}).get("pipeline_status"),
                "has_celery_task": bool((pipeline_associated or {}).get("celery_task_id")),
            },
        )

    return {"success": True}

@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: str):
    result = db.vehicle_state.delete_one({"vehicle_id": vehicle_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
        
    emit_activity_event(
        vehicle_id=vehicle_id,
        source_type="api",
        source_name="vehicle_delete_route",
        stage_from="IDLE",
        stage_to="IDLE",
        action="vehicle_deleted",
        status="success",
        summary="Vehicle was permanently deleted.",
    )
    
    return {"success": True, "deleted": True}
