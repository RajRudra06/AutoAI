import os
from dotenv import load_dotenv
from tasks_celery.celery_app import app  # Assuming celery_app is correctly configured
from agents.utils.agent_api_client import post

load_dotenv()

# This is the execution layer logic extracted from MasterAgent.put_diagnosis_job
@app.task
def queue_diagnosis_job(vehicle_id: str, features_snapshot: dict, trigger_reasons: dict, latest_feature_associated_telemetryID: str):
    """
    Celery task to queue a diagnosis job and update the vehicle's state.
    This represents the execution layer of the Master Agent's diagnosis decision.
    """
    api_base_url = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

    try:
        print(f"[CELERY_TASK][DIAGNOSIS_JOB] Sending diagnosis job for {vehicle_id}")

        # 1. Queue the diagnosis job via the backend API
        post(
            f"{api_base_url}/api/diagnosis/queue",
            json={
                "vehicle_id": vehicle_id,
                "features_snapshot": features_snapshot,
                "trigger_reasons": trigger_reasons
            }
        )

        print(f"[CELERY_TASK][DIAGNOSIS_JOB] {vehicle_id} → DIAGNOSIS_PENDING")

        # 2. Update the vehicle's temp_last_processed_telemetry
        print(
            f"[CELERY_TASK][DIAGNOSIS_JOB] Updating temp_last_processed_telemetry="
            f"{latest_feature_associated_telemetryID}"
        )

        post(
            f"{api_base_url}/api/vehicles/update",
            json={
                "vehicle_id": vehicle_id,
                "temp_last_processed_telemetry": latest_feature_associated_telemetryID
            }
        )

        print(f"[CELERY_TASK][DIAGNOSIS_JOB] temp_last_processed_telemetry updated for {vehicle_id}")

    except Exception as e:
        print(
            f"[CELERY_TASK][DIAGNOSIS_JOB][ERROR] Failed to queue diagnosis job for {vehicle_id}: {e}"
        )

# diagnosis task (claude.ai)

# tasks/diagnosis_tasks.py

from tasks.celery_app import app
from celery.utils.log import get_task_logger
from datetime import datetime, timezone
import joblib
import numpy as np

from backend.db.connection import db
from helpers.logic.get_feature_name import get_feature_names
from helpers.logic.risk_scoring import transform_scores_to_risk
from agents.utils.agent_api_client import post

logger = get_task_logger(__name__)

# Load ML model once
MODEL_PATH = "diag_agent_model/iForest/models/isolation_forest_v1.pkl"
FEATURE_ORDER = get_feature_names()
MODEL = joblib.load(MODEL_PATH)

logger.info(f"[DIAGNOSIS TASK] Model loaded from {MODEL_PATH}")


@app.task(
    bind=True,
    name='tasks.diagnosis_tasks.run_diagnosis',
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def run_diagnosis(self, vehicle_id: str, features_snapshot: dict, trigger_reasons: list, api_base_url: str, latest_feature_associated_telemetryID):
    """
    Celery task: Execute diagnosis work
    This contains the actual execution (ML inference + DB updates)
    """
    logger.info(f"[DIAGNOSIS TASK] Processing {vehicle_id}")
    
    # Call the actual work function
    return put_diagnosis_job(
        vehicle_id=vehicle_id,
        features_snapshot=features_snapshot,
        trigger_reasons=trigger_reasons,
        api_base_url=api_base_url,
        latest_feature_associated_telemetryID=latest_feature_associated_telemetryID
    )


def put_diagnosis_job(vehicle_id: str, features_snapshot: dict, trigger_reasons: dict, api_base_url: str, latest_feature_associated_telemetryID):
    """
    EXACT COPY from original MasterAgent.put_diagnosis_job()
    This is the EXECUTION work that was in the old master agent
    """
    try:
        print(f"[DIAGNOSIS TASK][QUEUE] Sending diagnosis job for {vehicle_id}")

        post(
            f"{api_base_url}/api/diagnosis/queue",
            json={
                "vehicle_id": vehicle_id,
                "features_snapshot": features_snapshot,
                "trigger_reasons": trigger_reasons
            }
        )

        print(f"[DIAGNOSIS TASK][QUEUE] {vehicle_id} → DIAGNOSIS_PENDING")

        print(
            f"[DIAGNOSIS TASK][UPDATE] Updating temp_last_processed_telemetry="
            f"{latest_feature_associated_telemetryID}"
        )

        print(latest_feature_associated_telemetryID)
        reply = post(
            f"{api_base_url}/api/vehicles/update",
            json={
                "vehicle_id": vehicle_id,
                "temp_last_processed_telemetry": latest_feature_associated_telemetryID
            }
        )

        print(reply)

        print(f"[DIAGNOSIS TASK][UPDATE] temp_last_processed_telemetry updated")
        
        return {"status": "success", "vehicle_id": vehicle_id}

    except Exception as e:
        print(f"[DIAGNOSIS TASK][ERROR] Failed to queue {vehicle_id}: {e}")
        raise