from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import random
from datetime import datetime, timezone
from backend.db.connection import db
from backend.activity.helpers import emit_activity_event

router = APIRouter(prefix="/telematics", tags=["Telemetry"])

@router.post("/data")
def receive_telemetry(payload: dict):

    vehicle_id = payload["vehicle_id"]
    features = payload["features"]

    now = datetime.now(timezone.utc)

    latest_telemetry_ID=payload.get("timestamp", now)

    if isinstance(latest_telemetry_ID, str):
        latest_telemetry_ID = (
            datetime.fromisoformat(latest_telemetry_ID)
            .replace(tzinfo=timezone.utc)
        )

    db.telemetry.insert_one({
        "vehicle_id": vehicle_id,
        "telemetryID": latest_telemetry_ID,
        "features": features,
        "status":"new"
    })

    existing_state = db.vehicle_state.find_one(
        {"vehicle_id": vehicle_id},
        {"latest_features": 1}
    )

    previous_features = (
        existing_state["latest_features"]
        if existing_state and "latest_features" in existing_state
        else None
    )

    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {
            "$set": {
                "vehicle_id": vehicle_id,
                "latest_features": features,
                "previous_features": previous_features,
                "latest_feature_associated_telemetryID":latest_telemetry_ID,
                "last_updated": now,
            },
            "$setOnInsert": {
                "version":1,
                "logID_reset":False,
                "pipeline_associated":{
                    "pipeline_status":"TELEMETRY_INITIATED",
                    "pipeline_assigned_at":datetime(1968, 1, 1, tzinfo=timezone.utc),
                    "celery_task_id": None
                },
                "temp_last_processed_telemetry":datetime(1969, 1, 1, tzinfo=timezone.utc),
                "last_processed_telemetry":datetime(1970, 1, 1, tzinfo=timezone.utc),
                "workflow_state": {
                    "current_stage": "IDLE",
                    "flags": {
                        "diagnosis_required": False,
                        "scheduling_required": False,
                        "engagement_required": False,
                    }
                },
                "risk_state": {
                    "high_risk_active": False,
                    "unresolved_issues": []
                }
            }
        },
        upsert=True
    )

    emit_activity_event(
        vehicle_id=vehicle_id,
        source_type="api",
        source_name="telemetry_route",
        stage_from="IDLE",
        stage_to="IDLE",
        action="telemetry_received",
        status="success",
        summary="Telemetry ingested and vehicle state refreshed.",
        details={"feature_count": len(features or {})},
    )

    return {"success": True}

@router.websocket("/ws/{vehicle_id}")
async def telemetry_websocket(websocket: WebSocket, vehicle_id: str):
    await websocket.accept()
    print(f"[TELEMETRY WS] Client connected for vehicle {vehicle_id}")
    
    # Initial state for simulation
    speed = random.uniform(50.0, 70.0)
    battery = random.uniform(85.0, 92.0)
    temp = random.uniform(88.0, 92.0)
    oil = random.uniform(94.0, 96.0)
    pressure = random.uniform(32.0, 33.0)
    odometer = random.uniform(12400.0, 12500.0)
    rpm = random.uniform(1800.0, 2200.0)
    fuel = random.uniform(65.0, 70.0)
    coolant = random.uniform(16.0, 18.0)
    intake = random.uniform(38.0, 42.0)
    throttle = random.uniform(15.0, 25.0)
    brake = random.uniform(82.0, 84.0)

    try:
        while True:
            # Simulate realistic fluctuations
            speed = max(0, min(140, speed + random.uniform(-2.5, 2.5)))
            battery = max(0, battery - random.uniform(0.005, 0.02)) # Slow drain
            temp = max(70, min(110, temp + random.uniform(-0.5, 0.6)))
            pressure = max(28, min(38, pressure + random.uniform(-0.05, 0.05)))
            odometer += (speed / 3600.0)
            rpm = max(800, min(6500, rpm + speed * 0.1 + random.uniform(-50, 50)))
            fuel = max(0, fuel - random.uniform(0.001, 0.005))
            coolant = max(10, min(25, coolant + random.uniform(-0.1, 0.1)))
            intake = max(20, min(60, intake + random.uniform(-0.2, 0.2)))
            throttle = max(0, min(100, (speed / 1.4) + random.uniform(-5, 5)))

            data = {
                "vehicle_id": vehicle_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sensors": {
                    "speed_kmph": round(speed, 1),
                    "battery_percent": round(battery, 2),
                    "engine_temp_c": round(temp, 1),
                    "oil_health_percent": round(oil, 1),
                    "tire_pressure_psi": round(pressure, 1),
                    "odometer_km": round(odometer, 3),
                    "engine_rpm": round(rpm, 0),
                    "fuel_level_percent": round(fuel, 1),
                    "coolant_pressure_psi": round(coolant, 1),
                    "intake_air_temp_c": round(intake, 1),
                    "throttle_pos_percent": round(throttle, 1),
                    "brake_pad_wear_percent": round(brake, 1)
                }
            }
            await websocket.send_json(data)
            await asyncio.sleep(1) 
            
    except WebSocketDisconnect:
        print(f"[TELEMETRY WS] Client disconnected for vehicle {vehicle_id}")
    except Exception as e:
        print(f"[TELEMETRY WS] Error: {e}")
        await websocket.close()
