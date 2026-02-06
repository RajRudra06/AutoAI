# tasks/diagnosis_tasks.py

from .celery_config import app
from celery.utils.log import get_task_logger
from datetime import datetime, timezone
import joblib
import numpy as np

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
    name='task.diagnosis.run_diagnosis',
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)

def run_diagnosis(self, vehicle_id: str, features_snapshot: dict, trigger_reasons: list, api_base_url: str, latest_feature_associated_telemetryID,thread_id:int,master_shard_id:int):
   
    logger.info(f"[DIAGNOSIS TASK] Processing {vehicle_id} on shard {master_shard_id} with thread {thread_id}")
    
    return put_diagnosis_job(
        vehicle_id=vehicle_id,
        features_snapshot=features_snapshot,
        trigger_reasons=trigger_reasons,
        api_base_url=api_base_url,
        latest_feature_associated_telemetryID=latest_feature_associated_telemetryID,
        master_shard_id=master_shard_id,
        thread_id=thread_id
    )


def put_diagnosis_job(vehicle_id: str, features_snapshot: dict, trigger_reasons: dict, api_base_url: str, latest_feature_associated_telemetryID,master_shard_id:int,thread_id:int):

    try:
        print(f"[DIAGNOSIS TASK][QUEUE] Sending diagnosis job for {vehicle_id} for shard {master_shard_id} with thread {thread_id}")

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