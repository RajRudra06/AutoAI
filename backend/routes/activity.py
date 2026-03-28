from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.activity.event_bus import event_bus
from backend.activity.service import store_activity_event
from backend.db.connection import db
from worker_tasks.celery_config import app as celery_app

router = APIRouter(prefix="/activity", tags=["Activity"])

QUEUE_NAMES = [
    "diagnosis_queue",
    "execution_diagnosis_task_queue",
    "scheduling_queue",
    "engagement_queue",
    "service_completion_queue",
    "default",
]


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

    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    events_last_hour = db.activity_events.count_documents({"timestamp": {"$gte": one_hour_ago}})
    stale_or_failed = db.activity_events.count_documents({"status": {"$in": ["failed", "stale"]}})

    vehicle_stage_counts = Counter()
    high_risk_count = 0
    active_vehicle_count = 0
    for vehicle in db.vehicle_state.find({}, {"workflow_state": 1, "risk_state": 1}):
        stage = (
            vehicle.get("workflow_state", {})
            .get("current_stage")
            or "UNKNOWN"
        )
        vehicle_stage_counts[stage] += 1

        if vehicle.get("risk_state", {}).get("high_risk_active"):
            high_risk_count += 1

        if stage != "IDLE":
            active_vehicle_count += 1

    return {
        "window_events": window_events,
        "recent_event_count": len(recent_events),
        "events_last_hour": events_last_hour,
        "events_per_minute": round(events_last_hour / 60, 2),
        "stale_or_failed_events": stale_or_failed,
        "active_vehicle_count": active_vehicle_count,
        "high_risk_vehicle_count": high_risk_count,
        "fleet_stage_counts": dict(vehicle_stage_counts),
        "status_counts": status_counts,
        "source_counts": source_counts,
        "transition_counts": transition_counts,
    }


def _queue_depths_from_redis() -> tuple[dict[str, int], str]:
    try:
        with celery_app.connection_for_read() as connection:
            transport_type = getattr(connection.transport, "driver_type", "")
            if transport_type != "redis":
                return ({name: 0 for name in QUEUE_NAMES}, "unsupported_broker")

            channel = connection.channel()
            client = getattr(channel, "client", None)
            if client is None:
                return ({name: 0 for name in QUEUE_NAMES}, "broker_client_unavailable")

            queue_depths: dict[str, int] = {}
            for queue_name in QUEUE_NAMES:
                try:
                    queue_depths[queue_name] = int(client.llen(queue_name))
                except Exception:
                    queue_depths[queue_name] = 0

            try:
                channel.close()
            except Exception:
                pass

            return (queue_depths, "ok")
    except Exception:
        return ({name: 0 for name in QUEUE_NAMES}, "redis_unreachable")


def _worker_heartbeat_snapshot() -> dict[str, Any]:
    inspector = celery_app.control.inspect(timeout=1.5)

    try:
        stats = inspector.stats() or {}
    except Exception:
        stats = {}

    workers: dict[str, Any] = {}
    for worker_name, worker_stats in stats.items():
        workers[worker_name] = {
            "online": True,
            "pid": worker_stats.get("pid"),
            "pool": worker_stats.get("pool", {}).get("max-concurrency"),
            "total_tasks": sum((worker_stats.get("total") or {}).values()),
        }

    return {
        "online_worker_count": len(workers),
        "workers": workers,
        "status": "ok" if workers else "no_workers_detected",
    }


def _build_health_trends(window_events: int = 240, points: int = 24) -> dict[str, Any]:
    rows = list(
        db.activity_events
        .find({}, {"status": 1, "latency_ms": 1, "timestamp": 1})
        .sort("timestamp", -1)
        .limit(window_events)
    )

    if not rows:
        return {
            "latency_ms_trend": [0] * points,
            "retry_signal_trend": [0] * points,
            "avg_latency_ms": 0.0,
            "retry_signal_percent": 0.0,
        }

    rows = list(reversed(rows))
    latencies = [
        float(r.get("latency_ms"))
        for r in rows
        if isinstance(r.get("latency_ms"), (int, float))
    ]
    avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    signal_set = {"failed", "stale", "skipped"}
    signal_count = sum(1 for r in rows if (r.get("status") or "").lower() in signal_set)
    retry_signal_percent = round((signal_count / max(1, len(rows))) * 100, 2)

    bucket_size = max(1, len(rows) // points)
    latency_trend: list[int] = []
    retry_trend: list[int] = []

    for idx in range(points):
        start = idx * bucket_size
        end = start + bucket_size
        chunk = rows[start:end]

        if not chunk:
            latency_trend.append(0)
            retry_trend.append(0)
            continue

        chunk_latencies = [
            float(item.get("latency_ms"))
            for item in chunk
            if isinstance(item.get("latency_ms"), (int, float))
        ]
        if chunk_latencies:
            latency_trend.append(int(round(sum(chunk_latencies) / len(chunk_latencies))))
        else:
            latency_trend.append(0)

        chunk_signals = sum(1 for item in chunk if (item.get("status") or "").lower() in signal_set)
        retry_trend.append(int(round((chunk_signals / max(1, len(chunk))) * 100)))

    return {
        "latency_ms_trend": latency_trend,
        "retry_signal_trend": retry_trend,
        "avg_latency_ms": avg_latency_ms,
        "retry_signal_percent": retry_signal_percent,
    }


@router.get("/metrics/health")
def get_queue_and_worker_health():
    queue_depths, queue_status = _queue_depths_from_redis()
    heartbeat = _worker_heartbeat_snapshot()
    trends = _build_health_trends()

    total_queue_depth = sum(queue_depths.values())
    max_depth = max(queue_depths.values()) if queue_depths else 0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue_status": queue_status,
        "queue_depths": queue_depths,
        "total_queue_depth": total_queue_depth,
        "max_queue_depth": max_depth,
        "worker_heartbeat": heartbeat,
        "latency_ms_trend": trends["latency_ms_trend"],
        "retry_signal_trend": trends["retry_signal_trend"],
        "avg_latency_ms": trends["avg_latency_ms"],
        "retry_signal_percent": trends["retry_signal_percent"],
    }


def _render_journey_summaries(vehicle_id: str, events: list[dict[str, Any]]) -> dict[str, str]:
    if not events:
        return {
            "technical_summary": f"No lifecycle events recorded yet for vehicle {vehicle_id}.",
            "business_summary": f"Vehicle {vehicle_id} has no processed journey yet.",
            "judge_summary": f"Vehicle {vehicle_id} has no journey events yet.",
        }

    first_ts = events[0].get("timestamp")
    last_ts = events[-1].get("timestamp")
    duration_minutes = 0.0
    if isinstance(first_ts, datetime) and isinstance(last_ts, datetime):
        duration_minutes = max((last_ts - first_ts).total_seconds() / 60.0, 0.0)

    statuses = Counter((e.get("status") or "info") for e in events)
    transitions = [
        f"{e.get('stage_from') or 'UNKNOWN'}->{e.get('stage_to') or 'UNKNOWN'}"
        for e in events
    ]
    top_transitions = Counter(transitions).most_common(5)
    transition_text = ", ".join([f"{t}({c})" for t, c in top_transitions]) or "n/a"

    technical_summary = (
        f"Vehicle {vehicle_id} produced {len(events)} lifecycle events over "
        f"{duration_minutes:.1f} minutes. Status mix: {dict(statuses)}. "
        f"Top transitions: {transition_text}."
    )

    high_risk_events = sum(1 for e in events if (e.get("risk_level") or "").upper() == "HIGH")
    business_summary = (
        f"Vehicle {vehicle_id} moved through the service pipeline with {len(events)} tracked steps. "
        f"{high_risk_events} event(s) were marked high risk, enabling timely escalation and coordinated action "
        f"across diagnosis, scheduling, engagement, and closure."
    )

    judge_summary = (
        f"AutoAI tracked vehicle {vehicle_id} end-to-end with {len(events)} auditable events, "
        f"live stage transitions, and clear risk signals for operator-ready decisioning."
    )

    return {
        "technical_summary": technical_summary,
        "business_summary": business_summary,
        "judge_summary": judge_summary,
    }


@router.post("/summary/{vehicle_id}")
def generate_vehicle_summary(
    vehicle_id: str,
    window_events: int = Query(default=300, ge=20, le=2000),
):
    events = list(
        db.activity_events
        .find({"vehicle_id": vehicle_id})
        .sort("timestamp", 1)
        .limit(window_events)
    )

    summary = _render_journey_summaries(vehicle_id=vehicle_id, events=events)
    now = datetime.now(timezone.utc)
    doc = {
        "vehicle_id": vehicle_id,
        "generated_at": now,
        "window_events": window_events,
        "event_count": len(events),
        "technical_summary": summary["technical_summary"],
        "business_summary": summary["business_summary"],
        "judge_summary": summary["judge_summary"],
    }

    db.activity_summaries.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": doc},
        upsert=True,
    )

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "generated_at": now.isoformat(),
        "summary": summary,
        "event_count": len(events),
    }


@router.get("/summary/{vehicle_id}")
def get_vehicle_summary(vehicle_id: str):
    doc = db.activity_summaries.find_one({"vehicle_id": vehicle_id})
    if not doc:
        return {
            "success": False,
            "vehicle_id": vehicle_id,
            "message": "summary_not_found",
        }

    doc["_id"] = str(doc["_id"])
    if isinstance(doc.get("generated_at"), datetime):
        doc["generated_at"] = doc["generated_at"].isoformat()

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "summary": doc,
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
