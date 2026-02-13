import time
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
import requests 

from agents.utils.agent_api_client import post, get
from worker_tasks.celery_config import app 
load_dotenv()

BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

FEEDBACK_LOG_URL = f"{BASE_API_URL}/api/feedback/log"
SCHEDULE_UPDATE_URL = f"{BASE_API_URL}/api/schedule/update"
VEHICLES_UPDATE_URL = f"{BASE_API_URL}/api/vehicles/update"


@app.task(
    bind=True,
    name='tasks.execute_service_completion.execute_service_completion_job', 
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def execute_service_completion_job(self, vehicle_id: str, base_api_url: str, temp_last_processed_telemetry: datetime, risk_state: dict):
    my_task_id = self.request.id
    print(f"[SERVICE COMPLETION TASK] Starting execution for vehicle {vehicle_id}, task_id={my_task_id}")

    print(f"Task {my_task_id}: Verifying state for vehicle {vehicle_id} before execution.")
    try:
        vehicle_state_resp = get(f"{base_api_url}/api/vehicles/state/{vehicle_id}")
        vehicle_state_resp.raise_for_status()
        current_vehicle_data = vehicle_state_resp.json()
    except Exception as e:
        print(f"Task {my_task_id}: ABORTING. Could not fetch state for vehicle {vehicle_id}. Error: {e}")
       
        return 

    pipeline_data = current_vehicle_data.get("pipeline_associated", {})

    if not (
        pipeline_data.get("pipeline_status") == "ASSIGNED_BY_SERVICE_COMPLETION_AGENT" 
        and pipeline_data.get("celery_task_id") == my_task_id
    ):
        print(
            f"Task {my_task_id}: ABORTING. Task is stale or has been superseded. "
            f"Vehicle {vehicle_id} has been reset or assigned a new task."
        )
        return 

    print(f"Task {my_task_id}: Pre-execution check passed. Completing service for {vehicle_id}.")

    print(f"[SERVICE COMPLETION TASK] Updating vehicle schedule for {vehicle_id}")
    if not update_vehicle_schedule_celery(vehicle_id, base_api_url):
        print(f"[SERVICE COMPLETION TASK][ERROR] Failed to update vehicle schedule for {vehicle_id}")
        return

    print(f"[SERVICE COMPLETION TASK] Updating vehicle state for {vehicle_id}")
    if not update_vehicle_state_celery(vehicle_id, base_api_url, temp_last_processed_telemetry, risk_state):
        print(f"[SERVICE COMPLETION TASK][ERROR] Failed to update vehicle state for {vehicle_id}")
        return

    print(f"[SERVICE COMPLETION TASK] Completing logging for {vehicle_id}")
    if not post_feedback_log_celery(vehicle_id, base_api_url):
        print(f"[SERVICE COMPLETION TASK][ERROR] Failed to post feedback log for {vehicle_id}")
        return

    print(f"[SERVICE COMPLETION TASK] Lifecycle closed for {vehicle_id}")

    return f"Completed service completion for vehicle {vehicle_id}"

def post_feedback_log_celery(vehicle_id: str, base_api_url: str) -> bool:
    feedback_log_api = f"{base_api_url}/api/feedback/log"
    post_feedback_log_resp = post(feedback_log_api, json={
        "vehicle_id": vehicle_id,
        "message": "Service completed successfully",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    if post_feedback_log_resp.status_code == 200:
        return True
    print(f"[SERVICE COMPLETION TASK][ERROR] Failed to post feedback log. Status: {post_feedback_log_resp.status_code}")
    return False

def update_vehicle_state_celery(vehicle_id: str, base_api_url: str, temp_last_processed_telemetry: datetime, risk_state: dict) -> bool:
    update_vehicle_state_api = f"{base_api_url}/api/vehicles/update"
    update_vehicle_state_resp = post(update_vehicle_state_api, json={
        "vehicle_id": vehicle_id,
        "last_processed_telemetry": temp_last_processed_telemetry.isoformat() if isinstance(temp_last_processed_telemetry, datetime) else temp_last_processed_telemetry, 
        "workflow_state": {
            "current_stage": "IDLE",
            "flags": {
                "diagnosis_required": False,
                "scheduling_required": False,
                "engagement_required": False
            }
        },
        "risk_state": {
            "high_risk_active": False,
            "unresolved_issues": []
        }
    })
    if update_vehicle_state_resp.status_code == 200:
        return True
    print(f"[SERVICE COMPLETION TASK][ERROR] Failed to update vehicle state. Status: {update_vehicle_state_resp.status_code}")
    return False

def update_vehicle_schedule_celery(vehicle_id: str, base_api_url: str) -> bool:
    update_schedule_api = f"{base_api_url}/api/schedule/update"
    update_vehicle_schedule_resp = post(update_schedule_api, json={
        "vehicle_id": vehicle_id,
        "status": "COMPLETED",
        "completed_at": datetime.now(timezone.utc).isoformat()
    })
    if update_vehicle_schedule_resp.status_code == 200:
        return True
    print(f"[SERVICE COMPLETION TASK][ERROR] Failed to update vehicle schedule. Status: {update_vehicle_schedule_resp.status_code}")
    return False
