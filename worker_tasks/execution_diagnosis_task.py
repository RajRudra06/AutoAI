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


@app.task(
    bind=True,
    name='tasks.execute_diagnosis.execute_diagnosis_job',
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)

def execute_diagnosis_job(self,job_data: dict, base_api_url:str,window_size:int):
   
    job_id = job_data["_id"]
    vehicle_id = job_data["vehicle_id"]
    features_dict = job_data["features_snapshot"]
    unresolved_issues = job_data.get("trigger_reasons", [])

    my_task_id = self.request.id 

    print(f"[DIAGNOSIS TASK] Starting execution for job {job_id} for vehicle {vehicle_id}")

   
    print(f"Task {my_task_id}: Verifying state for vehicle {vehicle_id} before execution.")
    try:
    
        # get latest vehicle state
        vehicle_state_resp = get(f"{base_api_url}/api/vehicles/state/{vehicle_id}")
        vehicle_state_resp.raise_for_status()  
        current_vehicle_data = vehicle_state_resp.json()

        # get latest status of the current diagnosis job

        diagnosis_job_state_api=f"{base_api_url}/api/diagnosis/job/{job_id}"
        diagnosis_job_state_resp=get(diagnosis_job_state_api)
        curr_job_data=diagnosis_job_state_resp.json()

    except Exception as e:
            print(f"Task {my_task_id}: ABORTING. Could not fetch state for vehicle {vehicle_id}. Error: {e}")
            return  # Abort if we can't verify the state
    
    pipeline_data = current_vehicle_data.get("pipeline_associated", {})

    curr_job_status=curr_job_data.get("status","")

    if not (
        pipeline_data.get("pipeline_status") == "ASSIGNED_BY_DIAGNOSIS_AGENT"
        and pipeline_data.get("celery_task_id") == my_task_id
        
    ) or curr_job_status == "STALE_JOB":
        print(
            f"Task {my_task_id}: ABORTING. Task is stale or has been superseded. "
            f"Vehicle {vehicle_id} has been reset or assigned a new task."
        )

        # making a db call to update the diagnosis job status to stale and log the occurrence for monitoring and debugging purposes

        update_stale_diagnosis_job=finalise_stale_jobs(self=self,vehicle_id=vehicle_id, base_api_url=base_api_url)

        if update_stale_diagnosis_job:
            return

        return f"Task {my_task_id}: Failed to mark stale jobs for vehicle {vehicle_id}. Manual intervention may be required."
     

    # --- END OF VERIFICATION STEP ---

    print(f"Task {my_task_id}: Pre-execution check passed. Starting diagnosis by laoding model and running inference.")

    
    feature_order, model,DEFAULT_MODEL_VERSION = load_isolation_forest_model_task()

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
        model_version=DEFAULT_MODEL_VERSION,
        window_size=window_size,
    )

    # 3. Post the completion or failure
    if payload and payload.get("risk_level") == "HIGH":
        if not post_complete_job_task(payload, base_api_url):
            fail_job_post_task(job_id, vehicle_id, base_api_url)
            return f"Failed to complete job {job_id} with high risk"
        
    elif payload and payload.get("risk_level") == "LOW":
        if not complete_job_no_risk(job_id, vehicle_id, base_api_url,payload):
            fail_job_no_risk(job_id, vehicle_id, base_api_url)
            return f"Failed to complete job {job_id} with low risk"

    else:
        fail_job_post_task(job_id, vehicle_id, base_api_url)
        return f"Failed during inference for job {job_id}"
    
    return f"Completed job {job_id} for vehicle {vehicle_id}"

# Helper functions for the Celery task
def load_isolation_forest_model_task():

    # Load ML model once
    MODEL_PATH = "diag_agent_model/iForest/models/isolation_forest_v1.pkl"
    DEFAULT_MODEL_VERSION = os.getenv("DIAGNOSIS_MODEL_VERSION", "isolation_forest_v1")
    
    print("[DIAGNOSIS TASK] Loading ML model...")
    model = joblib.load(MODEL_PATH)
    FEATURE_ORDER = get_feature_names()
    print("[DIAGNOSIS TASK] Model loaded.")
    return FEATURE_ORDER, model, DEFAULT_MODEL_VERSION

def run_inference_task(feature_order:list, feature_dict:dict, model, unresolved_issues:list, vehicle_id:str, job_id:str, window_size:int,model_version:str)->dict:

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
  
    complete_job_api=f"{base_api_url}/api/diagnosis/complete"       
    post_complete_job_resp=post(complete_job_api,json=payload)

    if post_complete_job_resp.status_code==200:
        print(f"Diagnosis Job Posted: {payload['vehicle_id']}")
        return True
    print(f"Failed to post complete job for {payload['vehicle_id']}. Status Code: {post_complete_job_resp.status_code}")
    return False

def fail_job_post_task(job_id:str, vehicle_id:str, base_api_url:str):

    fail_job_api=f"{base_api_url}/api/diagnosis/fail"
    post_fail_job=post(fail_job_api,json={"job_id":job_id,"error":"error occurred while diagnosing the job"})
    print(f"[DIAGNOSIS TASK][ERROR] {vehicle_id} - Job failed.")

def start_job_post_task(job_id:str, base_api_url:str)->bool:

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
    
def complete_job_no_risk(job_id:str, vehicle_id:str, base_api_url:str, payload:dict):

    try:
        complete_no_risk_url=f"{base_api_url}/api/diagnosis/complete_job_no_risk"
        post_complete_no_risk_resp=post(complete_no_risk_url,json=payload)

        if post_complete_no_risk_resp.status_code == 200:
            print(f"Completed job with no risk: {vehicle_id}")
            return True
        print(f"Failed to complete no-risk job for {vehicle_id}. Status Code: {post_complete_no_risk_resp.status_code}")
        return False
    
    except Exception as e:
        print(f"Exception completing no-risk job for {vehicle_id}: {e}")
        return False

def fail_job_no_risk(job_id:str, vehicle_id:str, base_api_url:str):

    try:
        fail_no_risk_url=f"{base_api_url}/api/diagnosis/failed_job_no_risk"
        post_fail_no_risk_resp=post(fail_no_risk_url,json={"job_id":job_id,"error":"error occurred while completing no-risk job","vehicle_id":vehicle_id})
        print(f"[DIAGNOSIS TASK][ERROR] {vehicle_id} - No-risk job failed.")

        if post_fail_no_risk_resp.status_code == 200:
            return True
        return False
    except Exception as e:
        print(f"Exception failing no-risk job for {vehicle_id}: {e}")
        return False
    
def finalise_stale_jobs(self,vehicle_id:str, base_api_url:str):

    try:
        mark_stale_job_url=f"{base_api_url}/api/diagnosis/finalize/stale_diagnosis_jobs"
        mark_post_stale_job_resp=post(mark_stale_job_url,json={"vehicle_id":vehicle_id})
        print(f"[DIAGNOSIS TASK] Marked stale jobs for {vehicle_id}.")

        if mark_post_stale_job_resp.status_code == 200:
            return True
        return False
    except Exception as e:
        print(f"Exception marking stale jobs for {vehicle_id}: {e}")
        return False