from fastapi import APIRouter, HTTPException
from backend.db.connection import db
from datetime import datetime, timezone
from backend.activity.helpers import emit_activity_event

router = APIRouter(prefix="/simulation", tags=["Simulation Control"])

@router.post("/start/{vehicle_id}")
def start_simulation(vehicle_id: str):
    """
    Manually triggers the vehicle maintenance lifecycle by setting the 
    diagnosis_required flag. This is picked up by the Master Agent.
    """
    vehicle = db.vehicle_state.find_one({"vehicle_id": vehicle_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Set flags to trigger the agents
    update_doc = {
        "workflow_state.flags.diagnosis_required": True,
        "workflow_state.current_stage": "IDLE", # Ensure it starts from IDLE
        "pipeline_associated.pipeline_status": "MANUALLY_TRIGGERED",
        "last_updated": datetime.now(timezone.utc)
    }

    db.vehicle_state.update_one({"vehicle_id": vehicle_id}, {"$set": update_doc})

    emit_activity_event(
        vehicle_id=vehicle_id,
        source_type="simulation",
        source_name="simulation_control",
        stage_from="IDLE",
        stage_to="IDLE",
        action="simulation_started",
        status="success",
        summary="User manually triggered the vehicle service lifecycle.",
        details={"trigger": "frontend_button"}
    )

    return {"success": True, "message": f"Simulation context initiated for {vehicle_id}"}


@router.post("/force-risk/{vehicle_id}")
def force_risk_simulation(vehicle_id: str):
    """
    Forces the vehicle into a high-risk state by modifying its telemetry values
    and setting the high_risk_active flag. This provides a 'Coherent' source of truth
    for both the dashboard and live streams.
    """
    vehicle = db.vehicle_state.find_one({"vehicle_id": vehicle_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Manually inject 'Out of Bounds' telemetry
    latest_features = vehicle.get("latest_features", {})
    latest_features.update({
        "engine_temp_c": 128.5,
        "battery_percent": 7.2,
        "oil_health_percent": 15.4,
        "coolant_pressure_psi": 5.8,
        "throttle_pos_percent": 98.0
    })

    # Manually inject unresolved issues
    risk_state = {
        "high_risk_active": True,
        "unresolved_issues": [
            "Critical Thermal Runaway Detected",
            "Battery Voltage Collapse",
            "Oil System Pressure Warning"
        ]
    }

    update_doc = {
        "latest_features": latest_features,
        "risk_state": risk_state,
        "last_updated": datetime.now(timezone.utc)
    }

    db.vehicle_state.update_one({"vehicle_id": vehicle_id}, {"$set": update_doc})

    emit_activity_event(
        vehicle_id=vehicle_id,
        source_type="simulation",
        source_name="simulation_control",
        stage_from="NORMAL",
        stage_to="CRITICAL",
        action="system_breach_simulated",
        status="success",
        summary="User manually simulated a critical system breach.",
        details={"temp": 128.5, "battery": 7.2}
    )

    return {"success": True, "message": "System breach simulated with high-fidelity telemetry sync."}
