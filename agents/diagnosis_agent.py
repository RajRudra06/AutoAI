# diagnosis_agent.py
 
from datetime import datetime, timezone
import time
from dotenv import load_dotenv
import os
from celery.result import AsyncResult
from pytz import timezone 

from agents.utils.agent_api_client import post, get
from worker_tasks.execution_diagnosis_task import execute_diagnosis_job

load_dotenv()

class DiagnosisAgent:
    def __init__(self,base_api_url:str,poll_interval:int,model_path:str,window_size:int,model_version:str):
        self.poll_interval=poll_interval
        self.base_api_url=base_api_url
        self.model_path=model_path
        self.window_size=window_size
        self.model_version=model_version
    
    def get_diagnosis_jobs(self)->list:
        get_diagnosis_jobs_api=f"{self.base_api_url}/api/diagnosis/jobs"
        job_response=get(get_diagnosis_jobs_api)
        jobs=job_response.json().get("jobs",[])

        return jobs

    def extract_vehicle_params(self, vehicle: dict) -> dict:
        vehicle_id = vehicle["vehicle_id"]
        workflow = vehicle.get("workflow_state", {})
        risk_state = vehicle.get("risk_state", {})
        flags = workflow.get("flags", {})
        latest = vehicle.get("latest_features", {})
        previous = vehicle.get("previous_features", {})
        pipeline = vehicle.get("pipeline_associated") or {} 

        return {
            "vehicle_id": vehicle_id,
            "pipeline_associated": vehicle.get("pipeline_associated"),
            "celery_task_id": pipeline.get("celery_task_id"),
            # Workflow
            "workflow_stage": workflow.get("current_stage"),
            "workflow_flags": {
                "diagnosis_required": flags.get("diagnosis_required", False),
                "scheduling_required": flags.get("scheduling_required", False),
                "engagement_required": flags.get("engagement_required", False),
            },

            # Risk
            "high_risk_active": risk_state.get("high_risk_active", False),
            "unresolved_issues": risk_state.get("unresolved_issues", []),

            # Features (snapshots)
            "latest_features": latest,
            "previous_features": previous,

            "last_updated": vehicle.get("last_updated"),
            "temp_last_processed_telemetry": vehicle.get("temp_last_processed_telemetry"),
            "last_processed_telemetry": vehicle.get("last_processed_telemetry"),
            "latest_feature_associated_telemetryID": vehicle.get("latest_feature_associated_telemetryID"),
        }
    
    def process_jobs(self,jobs:list):
        for job in jobs:
            job_id=job["_id"]
            vehicle_id=job["vehicle_id"]

            vehicle_lifecycle_gate_check=self.lifecycle_gate_check(job_id=job_id,vehicle_id=vehicle_id)

            if vehicle_lifecycle_gate_check == True:
                continue

            print(f"[DIAGNOSIS DISPATCHER] Delegating job {job_id} for {vehicle_id} to Celery.")

            try:
                print(f"[DIAGNOSIS SHARD][ENQUEUE] Enqueuing execution diagnosis task for {vehicle_id}")

                res=execute_diagnosis_job.delay(
                    job,
                    self.base_api_url,
                    self.model_path,
                    self.window_size,
                    self.model_version
                )

                print(f"[DIAGNOSIS SHARD][ENQUEUE] Task enqueued, task_id=***********************************{res.id}")

                update_vehicle_state = post(
                f"{self.api_base_url}/api/vehicles/update",
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "ASSIGNED_BY_DIAGNOSIS_AGENT",
                        "pipeline_assigned_at": datetime.now(timezone.utc).isoformat(),
                        "celery_task_id":res.id
                        }
                    }
                )   

                if update_vehicle_state.status_code != 200:
                    print(f"[DIAGNOSIS SHARD][ERROR] Failed to update vehicle state for vehicle {vehicle_id}")
                    return

                print(f"[DIAGNOSIS SHARD][ENQUEUE] Task queued for {vehicle_id}, task_id={res.id}")

            except Exception as e:
                print(f"[DIAGNOSIS SHARD][ERROR] Task queueing failed, rolling back vehicle state: {e}")

                post(
                    f"{self.api_base_url}/api/vehicles/update",
                    json={
                        "vehicle_id": vehicle_id,
                        "pipeline_associated": {
                            "pipeline_status": "DIAGNOSIS_PENDING",
                            "pipeline_assigned_at": "1968-01-01T00:00:00Z"
                        }
                    }
                )

    def get_vehicle_state(self, vehicle_id: str) -> dict:
        get_vehicle_state_api = f"{self.base_api_url}/api/vehicles/state/{vehicle_id}"
        vehicle_resp = get(get_vehicle_state_api)

        if vehicle_resp.status_code == 200:
            vehicle_state = vehicle_resp.json()
            return vehicle_state
        
        return None
    
    def skip_job(self,job_id:str)->bool:
        skip_job_url=f"{self.base_api_url}/api/diagnosis/skip"

        skip_job=post(skip_job_url,json={"job_id":job_id,"reason":"Lifecycle gate active"})

        if skip_job.status_code==200:
            return True
        return False
        
    def lifecycle_gate_check(self, job_id: str, vehicle_id: str) -> bool:
        vehicle_state = self.get_vehicle_state(vehicle_id)

        # Add None check before using vehicle_state
        if vehicle_state is None:
            print(f"[DIAGNOSIS][ERROR] Could not fetch vehicle state for {vehicle_id}")
            print(vehicle_state)
            # Skip the job since we can't verify lifecycle state
            skip_current_vehicle_job = self.skip_job(job_id=job_id)
            if skip_current_vehicle_job == True:
                return True
            return False
        
        vehicle_state_params = self.extract_vehicle_params(vehicle=vehicle_state)

        workflow_stage = vehicle_state_params["workflow_stage"]
        high_risk = vehicle_state_params["high_risk_active"]
        last_processed_telemetry = vehicle_state_params["last_processed_telemetry"]
        latest_feature_associated_telemetryID = vehicle_state_params["latest_feature_associated_telemetryID"]
        pipeline_status = vehicle_state_params["pipeline_associated"].get("pipeline_status")
        pipeline_assigned_at=vehicle_state_params["pipeline_associated"].get("pipeline_assigned_at")
        scheduling_required=vehicle_state_params["workflow_flags"]["scheduling_required"]
        celery_task_id=vehicle_state_params["celery_task_id"]

        comparison_datetime = datetime.now(datetime.timezone.utc)
        now = datetime.now(datetime.timezone.utc)
        timeout=60

        if workflow_stage in {"DIAGNOSIS_COMPLETE", "SCHEDULING_COMPLETE", "ENGAGEMENT_COMPLETE"} or high_risk or last_processed_telemetry>=latest_feature_associated_telemetryID or pipeline_status != "ASSIGNED_BY_MASTER_AGENT" or (pipeline_assigned_at and pipeline_assigned_at > comparison_datetime):
            if(pipeline_status == "ASSIGNED_BY_DIAGNOSIS_AGENT" and pipeline_assigned_at and workflow_stage == "DIAGNOSIS_PENDING" and not scheduling_required and celery_task_id is not None):

                if(now-pipeline_assigned_at).total_seconds() > timeout: 
                    self.reset_stale_vehicle(vehicle=vehicle_state)
                    print(f"[DIAGNOSIS SHARD {self.shard_id}][GATE] Stale vehicle reset")

            print(f"[DIAGONSIS SHARD][GATE] Vehicle blocked by lifecycle gate")
            skip_current_vehicle_job = self.skip_job(job_id=job_id)
            if skip_current_vehicle_job == True:
                return True
                
        return False
    
    def reset_stale_vehicle(self, vehicle: dict):
        vehicle_state_api = f"{self.api_base_url}/api/vehicles/update"
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        vehicle_id=vehicle_state_params["vehicle_id"]
        pipeline_status = vehicle_state_params["pipeline_associated"].get("pipeline_status")
        pipeline_assigned_at=vehicle_state_params["pipeline_associated"].get("pipeline_assigned_at")
        scheduling_required=vehicle_state_params["workflow_flags"]["scheduling_required"]
        celery_task_id=vehicle_state_params["celery_task_id"]

        if celery_task_id:
            try:
                print(f"[DIAGNOSIS SHARD ][RESET] Revoking task {celery_task_id} for vehicle {vehicle_id}")
                AsyncResult(celery_task_id).revoke(terminate=True)
                print(f"[DIAGNOSIS SHARD {self.shard_id}][RESET] Task----------------------------------------------------------------------------- {celery_task_id} revoked successfully")
            except Exception as e:
                print(f"[DIAGNOSIS SHARD {self.shard_id}][RESET] Failed to revoke task {celery_task_id}: {e}")
                # Continue anyway - still reset the vehicle
        else:
            print(f"[DIAGNOSIS SHARD {self.shard_id}][RESET] No task_id found for vehicle {vehicle_id}, skipping revoke")

        # STEP 2: Reset vehicle state in DB
        try:
            update_req = post(
                vehicle_state_api,
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "DIAGNOSIS_PENDING",
                        "pipeline_assigned_at": "1968-01-01T00:00:00Z",
                        "celery_task_id": None  # ← Clear task ID
                    }
                }
            )
            
            if update_req.status_code == 200:
                print(f"[DIAGNOSIS SHARD][RESET] Vehicle {vehicle_id} reset successfully -----------------------------------------------------------------------------")
            else:
                print(f"[DIAGNOSIS SHARD][RESET] Failed to reset vehicle {vehicle_id}")

        except Exception as e:
            print(f"[DIAGNOSIS SHARD][RESET] Error resetting vehicle {vehicle_id}: {e}")


    def run(self):
        print("[DIAGNOSIS] Agent started. Waiting for jobs...")

        while True:
            get_diagnosis_jobs=self.get_diagnosis_jobs()
            self.process_jobs(get_diagnosis_jobs)

            time.sleep(self.poll_interval)

if __name__ == "__main__":
    base_api_url=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    model_path="diag_agent_model/iForest/models/isolation_forest_v1.pkl"
    poll_interval=20
    window_size=120
    model_version="isolation_forest_v1"

    diagnosis_agent=DiagnosisAgent(base_api_url=base_api_url,poll_interval=poll_interval,model_path=model_path,window_size=window_size,model_version=model_version)
    diagnosis_agent.run()
