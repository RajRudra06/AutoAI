from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from bson import ObjectId
from backend.db.connection import db

router = APIRouter(prefix="/diagnosis", tags=["Diagnosis"])

@router.get("/jobs")
def get_pending_jobs(limit: int = 5):
    jobs = list(
        db.diagnosis_jobs.find({"status": "PENDING"}).limit(limit)
    )

    for job in jobs:
        job["_id"] = str(job["_id"])

    return {"jobs": jobs}

@router.post("/start")
def start_diagnosis(payload: dict):
    job_id = ObjectId(payload["job_id"])

    res = db.diagnosis_jobs.update_one(
        {"_id": job_id, "status": "PENDING"},
        {
            "$set": {
                "status": "IN_PROGRESS",
                "started_at": datetime.now(timezone.utc)
            }
        }
    )

    if res.modified_count == 0:
        raise HTTPException(409, "Job already claimed")

    return {"success": True}

@router.post("/skip")
def skip_diagnosis(payload: dict):
    job_id = ObjectId(payload["job_id"])
    reason = payload.get("reason", "Lifecycle gate active")

    db.diagnosis_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "COMPLETED_SKIPPED",
                "skipped_at": datetime.now(timezone.utc),
                "skip_reason": reason
            }
        }
    )

    return {"success": True}

@router.post("/fail")
def fail_diagnosis(payload: dict):
    job_id = ObjectId(payload["job_id"])

    db.diagnosis_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "FAILED",
                "error": payload.get("error"),
                "failed_at": datetime.now(timezone.utc)
            }
        }
    )

    return {"success": True}

@router.post("/complete")
def complete_diagnosis(payload: dict):
    job_id = ObjectId(payload["job_id"])
    vehicle_id = payload["vehicle_id"]

    now = datetime.now(timezone.utc)

    db.predictions.insert_one({
        "vehicle_id": vehicle_id,
        "anomaly_score": payload["anomaly_score"],
        "risk_score": payload["risk_score"],
        "risk_level": payload["risk_level"],
        "features_snapshot": payload["features_snapshot"],
        "feature_version": payload["feature_version"],
        "window_size": payload["window_size"],
        "model_version": payload["model_version"],
        "created_at": now
    })

    db.vehicle_state.update_one(
        {"vehicle_id": vehicle_id},
        {
            "$set": {
                "workflow_state.current_stage": "DIAGNOSIS_COMPLETE",
                "workflow_state.flags.diagnosis_required": False,
                "workflow_state.flags.scheduling_required": True,
                "risk_state.high_risk_active": payload["risk_level"] == "HIGH",
                "risk_state.unresolved_issues": payload["unresolved_issues"],
                "last_diagnosis_at": now,
                "last_updated": now
            }
        }
    )

    db.diagnosis_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "COMPLETED",
                "completed_at": now
            }
        }
    )

    return {"success": True}


