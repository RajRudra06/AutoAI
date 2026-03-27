import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.activity.event_bus import event_bus
from backend.db.connection import db

_indexes_initialized = False


def _to_utc_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_activity_event(payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "event_id": payload.get("event_id") or str(uuid4()),
        "timestamp": _to_utc_datetime(payload.get("timestamp")),
        "vehicle_id": payload.get("vehicle_id", "UNKNOWN"),
        "source_type": payload.get("source_type", "system"),
        "source_name": payload.get("source_name", "unspecified"),
        "stage_from": payload.get("stage_from"),
        "stage_to": payload.get("stage_to"),
        "action": payload.get("action", "unknown_action"),
        "status": payload.get("status", "info"),
        "celery_task_id": payload.get("celery_task_id"),
        "job_id": payload.get("job_id"),
        "risk_level": payload.get("risk_level"),
        "summary": payload.get("summary", "No summary provided"),
        "details": payload.get("details") or {},
        "latency_ms": payload.get("latency_ms"),
    }
    return event


def _ensure_indexes() -> None:
    global _indexes_initialized
    if _indexes_initialized:
        return

    db.activity_events.create_index([("timestamp", -1)])
    db.activity_events.create_index([("vehicle_id", 1), ("timestamp", -1)])
    db.activity_events.create_index([("status", 1), ("timestamp", -1)])
    db.activity_events.create_index([("source_name", 1), ("timestamp", -1)])
    _indexes_initialized = True


def store_activity_event(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_indexes()
    event = build_activity_event(payload)
    db.activity_events.insert_one(event)

    event_for_stream = dict(event)
    event_for_stream["timestamp"] = event_for_stream["timestamp"].isoformat()

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(event_bus.publish(event_for_stream))
    except RuntimeError:
        # Called outside an active loop (e.g., sync contexts). Skip live push.
        pass

    return event
