import time
import joblib
import numpy as np
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

from backend.db.connection import db
from helpers.logic.get_feature_name import get_feature_names
from helpers.logic.risk_scoring import transform_scores_to_risk
from agents.utils.agent_api_client import post, get
from worker_tasks.celery_config import app

load_dotenv()

# Load ML model once
MODEL_PATH = "diag_agent_model/iForest/models/isolation_forest_v1.pkl"
FEATURE_ORDER = get_feature_names()
MODEL = joblib.load(MODEL_PATH)

print(f"[DIAGNOSIS TASK] Model loaded from {MODEL_PATH}")

@app.task(
    bind=True,
    name='tasks.execute_diagnosis.execute_diagnosis_job',
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)

def execute_diagnosis_job(self,job_data: dict, base_api_url:str, model_path:str, window_size:int, model_version:str):
   
    job_id = job_data["_id"]
    vehicle_id = job_data["vehicle_id"]
    features_dict = job_data["features_snapshot"]
    unresolved_issues = job_data.get("trigger_reasons", [])

    my_task_id = self.request.id # Get the unique ID of THIS task execution

    print(f"[DIAGNOSIS TASK] Starting execution for job {job_id} for vehicle {vehicle_id}")

    # Pre-execution verification step
    print(f"Task {my_task_id}: Verifying state for vehicle {vehicle_id} before execution.")
    try:
    # Fetch the most recent diagosis from the database via the API
        vehicle_state_resp = get(f"{base_api_url}/api/vehicles/state/{vehicle_id}")
        vehicle_state_resp.raise_for_status()  # Raise an exception for non-200 responses
        current_vehicle_data = vehicle_state_resp.json()
    except Exception as e:
            print(f"Task {my_task_id}: ABORTING. Could not fetch state for vehicle {vehicle_id}. Error: {e}")
            return  # Abort if we can't verify the state
    
    pipeline_data = current_vehicle_data.get("pipeline_associated", {})

     # THE CHECK: Is the vehicle still waiting for ME specifically?
    if not (
        pipeline_data.get("pipeline_status") == "ASSIGNED_BY_DIAGNOSIS_AGENT"
        and pipeline_data.get("celery_task_id") == my_task_id
    ):
        print(
            f"Task {my_task_id}: ABORTING. Task is stale or has been superseded. "
            f"Vehicle {vehicle_id} has been reset or assigned a new task."
        )
        return  # Silently exit without doing any work

    # --- END OF VERIFICATION STEP ---

    print(f"Task {my_task_id}: Pre-execution check passed. Starting diagnosis by laoding model and running inference.")

    # Load model (can be optimized with a persistent worker-side model if needed)
    feature_order, model = load_isolation_forest_model_task(model_path)

    # 1. Start the job
    if not start_job_post_task(job_id, base_api_url):
        fail_job_post_task(job_id, vehicle_id, base_api_url)
        return f"Failed to start job {job_id}"

    # 2. Run the ML inference
    payload = run_inference_task(
        feature_order=feature_order,
        feature_dict=features_dict,
        model=model,
        unresolved_issues=unresolved_issues,
        vehicle_id=vehicle_id,
        job_id=job_id,
        window_size=window_size,
        model_version=model_version
    )

    # 3. Post the completion or failure
    if payload:
        if not post_complete_job_task(payload, base_api_url):
            fail_job_post_task(job_id, vehicle_id, base_api_url)
            return f"Failed to complete job {job_id}"
    else:
        fail_job_post_task(job_id, vehicle_id, base_api_url)
        return f"Failed during inference for job {job_id}"
    
    return f"Completed job {job_id} for vehicle {vehicle_id}"

# Helper functions for the Celery task
def load_isolation_forest_model_task(model_path:str):
    """Loads the Isolation Forest model and feature order."""
    print("[DIAGNOSIS TASK] Loading ML model...")
    model = joblib.load(model_path)
    FEATURE_ORDER = get_feature_names()
    print("[DIAGNOSIS TASK] Model loaded.")
    return FEATURE_ORDER, model

def run_inference_task(feature_order:list, feature_dict:dict, model, unresolved_issues:list, vehicle_id:str, job_id:str, window_size:int, model_version:str)->dict:
    """Runs the machine learning inference for a single job."""
    X = np.array([[feature_dict[f] for f in feature_order]])

    anomaly_scores = model.score_samples(X)
    risk_scores = transform_scores_to_risk(anomaly_scores)

    anomaly_score = float(anomaly_scores[0])
    risk_score = float(risk_scores[0])
    is_anomaly = bool(model.predict(X)[0] == -1)

    risk_level = "HIGH" if is_anomaly else "LOW"
    
    payload = {
                "job_id": job_id,
                "vehicle_id": vehicle_id,
                "anomaly_score": anomaly_score,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "features_snapshot": feature_dict,
                "unresolved_issues": unresolved_issues,
                "feature_version": "v1",
                "window_size": window_size,
                "model_version": model_version
            }
    
    print(
                f"[DIAGNOSIS TASK][DONE] {vehicle_id} | "
                f"risk={risk_level} | score={risk_score:.3f}"
            )
        
    return payload

def post_complete_job_task(payload:dict, base_api_url:str)->bool:
    """Notifies the backend that a job is complete."""
    complete_job_api=f"{base_api_url}/api/diagnosis/complete"       
    post_complete_job_resp=post(complete_job_api,json=payload)

    if post_complete_job_resp.status_code==200:
        print(f"Diagnosis Job Posted: {payload['vehicle_id']}")
        return True
    print(f"Failed to post complete job for {payload['vehicle_id']}. Status Code: {post_complete_job_resp.status_code}")
    return False

def fail_job_post_task(job_id:str, vehicle_id:str, base_api_url:str):
    """Notifies the backend if a job failed."""
    fail_job_api=f"{base_api_url}/api/diagnosis/fail"
    post_fail_job=post(fail_job_api,json={"job_id":job_id,"error":"error occurred while diagnosing the job"})
    print(f"[DIAGNOSIS TASK][ERROR] {vehicle_id} - Job failed.")

def start_job_post_task(job_id:str, base_api_url:str)->bool:
    """Notifies the backend that a job is starting."""
    try:
        start_job_api=f"{base_api_url}/api/diagnosis/start"
        start_job_resp=post(start_job_api,json={"job_id":job_id})
        if start_job_resp.status_code == 200:
            return True
        print(f"Failed to start job {job_id}. Status Code: {start_job_resp.status_code}")
        return False
    except Exception as e:
        print(f"Exception starting job {job_id}: {e}")
        return False