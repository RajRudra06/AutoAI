from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.activity.event_bus import event_bus
from backend.activity.service import store_activity_event
from backend.db.connection import db

router = APIRouter(prefix="/activity", tags=["Activity"])


class ActivityEventPayload(BaseModel):
    event_id: str | None = None
    timestamp: datetime | str | None = None
    vehicle_id: str = Field(default="UNKNOWN")
    source_type: str = Field(default="system")
    source_name: str = Field(default="unspecified")
    stage_from: str | None = None
    stage_to: str | None = None
    action: str = Field(default="unknown_action")
    status: str = Field(default="info")
    celery_task_id: str | None = None
    job_id: str | None = None
    risk_level: str | None = None
    summary: str = Field(default="No summary provided")
    details: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | float | None = None


@router.post("/log")
def log_activity_event(payload: ActivityEventPayload):
    event = store_activity_event(payload.model_dump())
    event["timestamp"] = event["timestamp"].isoformat()
    return {"success": True, "event": event}


@router.get("/events")
def get_activity_events(
    vehicle_id: str | None = None,
    source_name: str | None = None,
    status: str | None = None,
    action: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
):
    filters: dict[str, Any] = {}
    if vehicle_id:
        filters["vehicle_id"] = vehicle_id
    if source_name:
        filters["source_name"] = source_name
    if status:
        filters["status"] = status
    if action:
        filters["action"] = action

    events = list(
        db.activity_events.find(filters).sort("timestamp", -1).skip(skip).limit(limit)
    )

    for event in events:
        event["_id"] = str(event["_id"])
        if isinstance(event.get("timestamp"), datetime):
            event["timestamp"] = event["timestamp"].isoformat()

    return {
        "events": events,
        "count": len(events),
        "filters": filters,
    }


@router.get("/vehicle/{vehicle_id}")
def get_vehicle_activity(vehicle_id: str, limit: int = Query(default=200, ge=1, le=1000)):
    events = list(
        db.activity_events
        .find({"vehicle_id": vehicle_id})
        .sort("timestamp", -1)
        .limit(limit)
    )

    for event in events:
        event["_id"] = str(event["_id"])
        if isinstance(event.get("timestamp"), datetime):
            event["timestamp"] = event["timestamp"].isoformat()

    return {
        "vehicle_id": vehicle_id,
        "events": events,
        "count": len(events),
    }


@router.get("/metrics/overview")
def get_activity_metrics_overview(window_events: int = Query(default=500, ge=50, le=5000)):
    recent_events = list(
        db.activity_events.find({}).sort("timestamp", -1).limit(window_events)
    )

    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    transition_counts: dict[str, int] = {}

    for event in recent_events:
        status = event.get("status") or "info"
        source = event.get("source_name") or "unspecified"
        stage_from = event.get("stage_from") or "UNKNOWN"
        stage_to = event.get("stage_to") or "UNKNOWN"
        transition_key = f"{stage_from}->{stage_to}"

        status_counts[status] = status_counts.get(status, 0) + 1
        source_counts[source] = source_counts.get(source, 0) + 1
        transition_counts[transition_key] = transition_counts.get(transition_key, 0) + 1

    return {
        "window_events": window_events,
        "recent_event_count": len(recent_events),
        "status_counts": status_counts,
        "source_counts": source_counts,
        "transition_counts": transition_counts,
    }


@router.websocket("/ws")
async def activity_events_websocket(websocket: WebSocket):
    await websocket.accept()
    queue = await event_bus.subscribe()

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        await event_bus.unsubscribe(queue)
    except Exception:
        await event_bus.unsubscribe(queue)
        await websocket.close()
