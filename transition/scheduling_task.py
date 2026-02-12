import time
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

from agents.utils.agent_api_client import post, get
from worker_tasks.celery_config import app # Assuming 'app' is the Celery app instance

load_dotenv()

@app.task(
    bind=True,
    name='tasks.execute_scheduling.execute_scheduling_job', # New task name
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def execute_scheduling_job(self, vehicle_id: str, base_api_url: str):
    my_task_id = self.request.id
    print(f"[SCHEDULING TASK] Starting execution for vehicle {vehicle_id}, task_id={my_task_id}")

    # Pre-execution verification step (similar to diagnosis_task)
    # Fetch the vehicle's state from the database via the API
    print(f"Task {my_task_id}: Verifying state for vehicle {vehicle_id} before execution.")
    try:
        vehicle_state_resp = get(f"{base_api_url}/api/vehicles/state/{vehicle_id}")
        vehicle_state_resp.raise_for_status()
        current_vehicle_data = vehicle_state_resp.json()
    except Exception as e:
        print(f"Task {my_task_id}: ABORTING. Could not fetch state for vehicle {vehicle_id}. Error: {e}")
        # In a real scenario, you might want to call a /fail endpoint for scheduling job here
        return # Abort if we can't verify the state

    pipeline_data = current_vehicle_data.get("pipeline_associated", {})

    # THE CHECK: Is the vehicle still waiting for ME specifically?
    # Ensure current_vehicle_data['pipeline_associated']['celery_task_id'] is aware of its own task_id
    if not (
        pipeline_data.get("pipeline_status") == "ASSIGNED_BY_SCHEDULING_AGENT"
        and pipeline_data.get("celery_task_id") == my_task_id
    ):
        print(
            f"Task {my_task_id}: ABORTING. Task is stale or has been superseded. "
            f"Vehicle {vehicle_id} has been reset or assigned a new task."
        )
        # You might want to call a /fail endpoint for scheduling job here if task is stale
        return # Silently exit without doing any work

    # --- END OF VERIFICATION STEP ---

    print(f"Task {my_task_id}: Pre-execution check passed. Attempting to schedule for {vehicle_id}.")

    # Original post_booking logic, adapted for Celery task
    get_booking_resp = get(f"{base_api_url}/api/schedule/{vehicle_id}")

    if get_booking_resp.status_code == 200 and get_booking_resp.headers.get("content-type", "").startswith("application/json"):
        data = get_booking_resp.json()
        booking = data.get("data")
        if isinstance(booking, dict) and booking: # Check if booking dict is not empty
            print(f"[SCHEDULING TASK] Booking already exists for {vehicle_id}, skipping new booking attempt.")
            # If booking already exists, update vehicle state to scheduling complete
            if update_vehicle_state_post_task(vehicle_id, base_api_url, current_stage="SCHEDULING_COMPLETE", scheduling_flag=False, engagement_flag=True):
                return f"Booking already exists for {vehicle_id}. Marked scheduling complete."
            else:
                print(f"[SCHEDULING TASK][ERROR] Failed to update vehicle state for {vehicle_id} after existing booking found.")
                # Implement a specific fail endpoint for scheduling tasks here if needed
                return f"Failed to update vehicle state for {vehicle_id} after existing booking found."

    print(f"[SCHEDULING TASK] Creating tentative booking for {vehicle_id}")

    slot_to_book = get_service_slot_post_task(base_api_url)

    if not slot_to_book:
        print(f"[SCHEDULING TASK][ERROR] Could not get service slot for {vehicle_id}.")
        # Implement a specific fail endpoint for scheduling tasks here if needed
        return f"Failed to get service slot for {vehicle_id}."

    booking_payload = {
        "vehicle_id": vehicle_id,
        "slot": slot_to_book,
        "center_id": "SC-01", # Hardcoded, might need to be dynamic
        "status": "TENTATIVE",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    if not post_final_booking_post_task(booking_payload, base_api_url):
        print(f"[SCHEDULING TASK][ERROR] Failed to post final booking for {vehicle_id}.")
        # Implement a specific fail endpoint for scheduling tasks here if needed
        return f"Failed to post final booking for {vehicle_id}."

    if not update_vehicle_state_post_task(vehicle_id, base_api_url, current_stage="SCHEDULING_COMPLETE", scheduling_flag=False, engagement_flag=True):
        print(f"[SCHEDULING TASK][ERROR] Failed to update vehicle state for {vehicle_id} after booking.")
        # Implement a specific fail endpoint for scheduling tasks here if needed
        return f"Failed to update vehicle state for {vehicle_id} after booking."

    print(f"[SCHEDULING TASK] Scheduling complete -> Engagement required for {vehicle_id}")

    return f"Completed scheduling for vehicle {vehicle_id}"

# Helper functions for the Celery task
def get_service_slot_post_task(base_api_url: str):
    service_slot_api = f"{base_api_url}/api/schedule/get_slot"
    service_slot_resp = get(service_slot_api)
    if service_slot_resp.status_code == 200:
        slot_to_book = service_slot_resp.text.strip('"') # Assuming raw text response is slot
        if slot_to_book:
            return slot_to_book
    print(f"[SCHEDULING TASK][ERROR] Failed to get service slot. Status: {service_slot_resp.status_code}")
    return None

def post_final_booking_post_task(booking_payload: dict, base_api_url: str):
    book_schedule_api = f"{base_api_url}/api/schedule/book"
    post_booking_resp = post(book_schedule_api, json=booking_payload)
    if post_booking_resp.status_code == 200:
        return True
    print(f"[SCHEDULING TASK][ERROR] Failed to post final booking. Status: {post_booking_resp.status_code}")
    return False

def update_vehicle_state_post_task(vehicle_id: str, base_api_url: str, current_stage: str, scheduling_flag: bool, engagement_flag: bool):
    update_state_api = f"{base_api_url}/api/schedule/update"
    update_state_resp = post(update_state_api, json={
        "vehicle_id": vehicle_id,
        "workflow_state": {
            "current_stage": current_stage,
            "flags": {
                "scheduling_required": scheduling_flag,
                "engagement_required": engagement_flag
            }
        },
        "pipeline_associated": { # Reset pipeline_associated after task completion
            "pipeline_status": "SCHEDULING_COMPLETE", # Assuming this means scheduling is done
            "pipeline_assigned_at": datetime.now(timezone.utc).isoformat(),
            "celery_task_id": None
        }
    })
    if update_state_resp.status_code == 200:
        return True
    print(f"[SCHEDULING TASK][ERROR] Failed to update vehicle state after scheduling. Status: {update_state_resp.status_code}")
    return False