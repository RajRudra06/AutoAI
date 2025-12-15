from fastapi import APIRouter
from datetime import datetime, timezone
from backend.db.connection import db

router = APIRouter(prefix="/telematics", tags=["Telemetry"])


@router.post("/data")
def receive_telemetry(payload: dict):
    """
    Responsibilities:
    1. Store full telemetry history
    2. Maintain per-vehicle latest + previous telemetry
    3. Do NOT touch workflow or risk flags
    """

    now = datetime.now(timezone.utc)

    # ----------------------------
    # 1️⃣ Store immutable telemetry history
    # ----------------------------
    telemetry_doc = {
        **payload,
        "timestamp": now
    }
    db.telemetry.insert_one(telemetry_doc)

    vehicle_id = payload["vehicle_id"]

    # ----------------------------
    # 2️⃣ Fetch existing state (if any)
    # ----------------------------
    existing_state = db.vehicle_state.find_one(
        {"vehicle_id": vehicle_id},
        {"latest_telemetry": 1}
    )

    previous_telemetry = None
    if existing_state and "latest_telemetry" in existing_state:
        previous_telemetry = existing_state["latest_telemetry"]

    # ----------------------------
    # 3️⃣ Update vehicle_state
    # ----------------------------
    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {
            "$set": {
                "vehicle_id": vehicle_id,
                "latest_telemetry": telemetry_doc,
                "previous_telemetry": previous_telemetry,
                "last_updated": now
            },
            "$setOnInsert": {
                # Initialize workflow & risk state ONLY on first insert
                "workflow_state": {
                    "current_stage": "IDLE",
                    "flags": {
                        "diagnosis_required": False,
                        "scheduling_required": False,
                        "engagement_required": False
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

    return {"success": True}
