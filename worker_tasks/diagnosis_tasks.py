# tasks/diagnosis_tasks.py

from .celery_config import app
from celery.utils.log import get_task_logger
from datetime import datetime, timezone
import joblib
import numpy as np

from helpers.logic.get_feature_name import get_feature_names
from helpers.logic.risk_scoring import transform_scores_to_risk
from agents.utils.agent_api_client import post,get


@app.task(
    bind=True,
    name='task.diagnosis.run_diagnosis',
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)

def run_diagnosis(
    self,
    vehicle_id: str,
    features_snapshot: dict,
    trigger_reasons: list,
    api_base_url: str,
    latest_feature_associated_telemetryID,
    thread_id: int,
    master_shard_id: int
):
    
    my_task_id = self.request.id  # Get the unique ID of THIS task execution

    # --- NEW: PRE-EXECUTION VERIFICATION STEP ---
    print(f"Task {my_task_id}: Verifying state for vehicle {vehicle_id} before execution.")

    try:
        # Fetch the most recent vehicle state from the database via the API
        vehicle_state_resp = get(f"{api_base_url}/api/vehicles/state/{vehicle_id}")
        vehicle_state_resp.raise_for_status()  # Raise an exception for non-200 responses
        current_vehicle_data = vehicle_state_resp.json()
    except Exception as e:
        print(f"Task {my_task_id}: ABORTING. Could not fetch state for vehicle {vehicle_id}. Error: {e}")
        return  # Abort if we can't verify the state

    pipeline_data = current_vehicle_data.get("pipeline_associated", {})
    
    # THE CHECK: Is the vehicle still waiting for ME specifically?
    if not (
        pipeline_data.get("pipeline_status") == "ASSIGNED_BY_MASTER_AGENT"
        and pipeline_data.get("celery_task_id") == my_task_id
    ):
        print(
            f"Task {my_task_id}: ABORTING. Task is stale or has been superseded. "
            f"Vehicle {vehicle_id} has been reset or assigned a new task."
        )
        return  # Silently exit without doing any work

    # --- END OF VERIFICATION STEP ---

    print(f"Task {my_task_id}: Pre-execution check passed. Starting diagnosis.")
    
    # If the check passes, proceed with the original logic
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