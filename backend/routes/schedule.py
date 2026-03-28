from fastapi import APIRouter
from backend.db.connection import db
from datetime import datetime, timezone,timedelta
import random
from backend.activity.helpers import emit_activity_event

router = APIRouter(prefix="/schedule", tags=["Scheduling"])


@router.post("/book")
def book_slot(payload: dict):
    payload.setdefault("created_at", datetime.now(timezone.utc))
    db.bookings.insert_one(payload)

    emit_activity_event(
        vehicle_id=payload.get("vehicle_id", "UNKNOWN"),
        source_type="api",
        source_name="schedule_route",
        stage_from="DIAGNOSIS_COMPLETE",
        stage_to="SCHEDULING_COMPLETE",
        action="booking_created",
        status="success",
        summary="Tentative service booking created.",
        details={"slot": payload.get("slot"), "center_id": payload.get("center_id")},
    )
    return {"success": True}


@router.get("/{vehicle_id}")
def get_booking(vehicle_id: str):
    appt = db.bookings.find_one(
        {"vehicle_id": vehicle_id},
        {"_id": 0}
    )

    if not appt or "created_at" not in appt:
        return {"data": False}

    vehicle = db.vehicle_state.find_one(
        {"vehicle_id": vehicle_id},
        {"_id": 0}
    )

    if not vehicle:
        return {"data": False}

    created_at = appt["created_at"]

    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    workflow_state = vehicle.get("workflow_state", {})
    flags = workflow_state.get("flags", {})

    current_stage = workflow_state.get("current_stage")
    scheduling_required = flags.get("scheduling_required", False)
    engagement_required = flags.get("engagement_required", False)

    if created_at < now and current_stage == "DIAGNOSIS_COMPLETE" and scheduling_required:
        return {"data": False}

    if created_at < now and current_stage == "SCHEDULING_COMPLETE" and engagement_required:
        return {"data": appt}

    return {"data": appt}

@router.get("/get_slot")
def generate_random_service_slot(days_ahead: int = 8) -> str:
  
    now = datetime.now(timezone.utc)

    day_offset = random.randint(1, days_ahead)
    service_date = now + timedelta(days=day_offset)

    hour = random.randint(9, 17)  
    minute = random.choice([0, 30])

    slot = service_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    return slot.isoformat()

    
@router.post("/update")
def update_vehicle_state(payload: dict):
    vehicle_id = payload["vehicle_id"]
    now = datetime.now(timezone.utc)

    update_doc = {"last_updated": now}

    if "workflow_state" in payload:
        update_doc["workflow_state"] = payload["workflow_state"]

    if "risk_state" in payload:
        update_doc["risk_state"] = payload["risk_state"]

    if "pipeline_associated.celery_task_id" in payload:
        update_doc["pipeline_associated.celery_task_id"] = payload["pipeline_associated.celery_task_id"]

    current = db.vehicle_state.find_one({"vehicle_id": vehicle_id}, {"workflow_state": 1, "_id": 0}) or {}
    previous_stage = (current.get("workflow_state") or {}).get("current_stage")

    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": update_doc}
    )

    workflow_state = payload.get("workflow_state") or {}
    next_stage = workflow_state.get("current_stage")
    if next_stage:
        emit_activity_event(
            vehicle_id=vehicle_id,
            source_type="api",
            source_name="schedule_route",
            stage_from=previous_stage,
            stage_to=next_stage,
            action="schedule_workflow_updated",
            status="success",
            summary="Scheduling workflow state updated.",
            details={"flags": workflow_state.get("flags") or {}},
        )

    return {"success": True}

@router.post("/complete_booking_schedule")
def complete_booking_schedule(payload: dict):
    vehicle_id = payload["vehicle_id"]
    now = datetime.now(timezone.utc)

    booking = db.bookings.find_one(
        {
            "vehicle_id": vehicle_id,
            "status": "TENTATIVE"
        }
    )

    if not booking:
        return {"success": False, "message": "No tentative booking found for vehicle"}

    result = db.bookings.update_one(
        {
            "_id": booking["_id"],
            "status": "TENTATIVE",
        },
        {
            "$set": {
                "status": "COMPLETE",
                "completed_at": now
            }
        }
    )

    if result.modified_count:
        emit_activity_event(
            vehicle_id=vehicle_id,
            source_type="api",
            source_name="schedule_route",
            stage_from="ENGAGEMENT_COMPLETE",
            stage_to="ENGAGEMENT_COMPLETE",
            action="booking_completed",
            status="success",
            summary="Service booking marked complete.",
            details={"vehicle_id": vehicle_id},
        )

    return {"success": bool(result.modified_count)}

   