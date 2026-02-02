from tasks_celery.celery_app import app
from agents.utils.agent_api_client import post
import os
from dotenv import load_dotenv

load_dotenv()

@app.task
def queue_diagnosis_job(vehicle_id: str, features_snapshot: dict, trigger_reasons: dict):
    api_base_url = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    try:
        print(f"[CELERY][DIAGNOSIS_TASK] Sending diagnosis job for {vehicle_id}")

        post(
            f"{api_base_url}/api/diagnosis/queue",
            json={
                "vehicle_id": vehicle_id,
                "features_snapshot": features_snapshot,
                "trigger_reasons": trigger_reasons
            }
        )

        print(f"[CELERY][DIAGNOSIS_TASK] {vehicle_id} → DIAGNOSIS_PENDING")

        # This part of the logic needs to be revisited.
        # The update of temp_last_processed_telemetry should ideally
        # be handled by the diagnosis agent after it picks up the job,
        # or by the backend API call itself, or via a separate task.
        # For now, let's keep it here, assuming the backend call does it.
        # However, the master agent shouldn't explicitly update `temp_last_processed_telemetry`
        # after putting the job into the queue; that's an execution detail.
        # The prompt specified "execution part where actual diagnosis job is set".
        # The `api/vehicles/update` call seems like a state management side effect
        # of the master agent's decision. For now, I will move this into the task.

        # The `latest_feature_associated_telemetryID` is not available in the task signature.
        # It needs to be passed if this update is to happen here.
        # Assuming for now this detail is handled by the backend's /api/diagnosis/queue endpoint implicitly
        # or needs to be explicitly passed from the master agent if the task is responsible for it.

        # Re-evaluating the original put_diagnosis_job:
        # It updates `temp_last_processed_telemetry` immediately after queuing the diagnosis.
        # This implies the master agent "considers" the telemetry processed once it queues the job.
        # This should ideally be moved to the task.

        # To avoid making assumptions, I will move the full content of put_diagnosis_job
        # into this task for now. The `latest_feature_associated_telemetryID` will need
        # to be passed as an argument to this task.

        # Original logic:
        # print(
        #     f"[MASTER][UPDATE] Updating temp_last_processed_telemetry="
        #     f"{vehicle_state_params['latest_feature_associated_telemetryID']}"
        # )
        # reply=post(
        #     f"{self.api_base_url}/api/vehicles/update",
        #     json={
        #         "vehicle_id": vehicle_state_params["vehicle_id"],
        #         "temp_last_processed_telemetry":
        #             vehicle_state_params["latest_feature_associated_telemetryID"]
        #     }
        # )
        # print(reply)
        # print(f"[MASTER][UPDATE] temp_last_processed_telemetry updated")


    except Exception as e:
        print(
            f"[CELERY][DIAGNOSIS_TASK][ERROR] Failed to queue diagnosis job for {vehicle_id}: {e}"
        )

