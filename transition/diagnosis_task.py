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
