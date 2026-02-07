import time
from dotenv import load_dotenv
import os

from agents.utils.agent_api_client import post, get
from transition.diagnosis_task import execute_diagnosis_job

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

        return {
            "vehicle_id": vehicle_id,

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
        }
    
    def process_jobs(self,jobs:list):
        for job in jobs:
            job_id=job["_id"]
            vehicle_id=job["vehicle_id"]

            vehicle_lifecycle_gate_check=self.lifecycle_gate_check(job_id=job_id,vehicle_id=vehicle_id)

            if vehicle_lifecycle_gate_check == True:
                continue

            print(f"[DIAGNOSIS DISPATCHER] Delegating job {job_id} for {vehicle_id} to Celery.")
            
            execute_diagnosis_job.delay(
                job,
                self.base_api_url,
                self.model_path,
                self.window_size,
                self.model_version
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

        vehicle_stage = vehicle_state_params["workflow_stage"]
        high_risk = vehicle_state_params["high_risk_active"]

        if vehicle_stage in {"DIAGNOSIS_COMPLETE", "SCHEDULING", "IN_SERVICE"} or high_risk:
            skip_current_vehicle_job = self.skip_job(job_id=job_id)
            if skip_current_vehicle_job == True:
                return True
                
        return False

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
