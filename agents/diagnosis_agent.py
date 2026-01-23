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

load_dotenv()

class DiagnosisAgent:
    def __init__(self,base_api_url:str,poll_interval:int,model_path:str,window_size:int,model_version:str):
        self.poll_interval=poll_interval
        self.base_api_url=base_api_url
        self.model_path=model_path
        self.window_size=window_size
        self.model_version=model_version

    def load_isolation_forest_model(self,model_path:str)->list[str]:
        print("[DIAGNOSIS] Loading ML model...")
        model = joblib.load(model_path)
        FEATURE_ORDER = get_feature_names()
        print("[DIAGNOSIS] Model loaded.")

        return FEATURE_ORDER,model
    
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
    
    def process_jobs(self,jobs:list,feature_order:list,model):
        for job in jobs:
            job_id=job["_id"]
            vehicle_id=job["vehicle_id"]
            features_dict = job["features_snapshot"]
            unresolved_issues = job.get("trigger_reasons", [])

            vehicle_lifecycle_gate_check=self.lifecycle_gate_check(job_id=job_id,vehicle_id=vehicle_id)

            if vehicle_lifecycle_gate_check == True:
                continue

            start_job_post=self.start_job_post(job_id=job_id)

            if start_job_post==False:
                continue

            print(f"[DIAGNOSIS] Processing {vehicle_id}")
            run_inference_on_vehicle=self.run_inference(feature_order=feature_order,feature_dict=features_dict,model=model,unresolved_issues=unresolved_issues,vehicle_id=vehicle_id,job_id=job_id)

            post_complete_job=self.post_complete_job(payload=run_inference_on_vehicle,vehicle_id=vehicle_id)

            if post_complete_job==False:
                self.fail_job_post(job_id=job_id,vehicle_id=vehicle_id)


    def run_inference(self,feature_order:list,feature_dict:dict,model,unresolved_issues:list,vehicle_id:str,job_id:str)->dict:
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
                    "window_size": self.window_size,
                    "model_version": self.model_version
                }
        
        print(
                    f"[DIAGNOSIS][DONE] {vehicle_id} | "
                    f"risk={risk_level} | score={risk_score:.3f}"
                )
         
        return payload

    def post_complete_job(self,payload:dict,vehicle_id:str)->bool:

        complete_job_api=f"{self.base_api_url}/api/diagnosis/complete"       

        post_complete_job_resp=post(complete_job_api,json=payload)

        if post_complete_job_resp.status_code==200:
            print(f"Diagnosis Job Posted: {vehicle_id}")
            return True
            
        return False
    
    def fail_job_post(self,job_id:str,vehicle_id:str):
        fail_job_api=f"{self.base_api_url}/api/diagnosis/fail"
        post_fail_job=post(fail_job_api,json={"job_id":job_id,"error":"error occured while diagnosing the job"})

        print(f"[DIAGNOSIS][ERROR] {vehicle_id}")
    

    def start_job_post(self,job_id:str)->bool:
        try:
            start_job_api=f"{self.base_api_url}/api/diagnosis/start"
            start_job_resp=post(start_job_api,json={"job_id":job_id})
            return True
        except Exception:
            return False

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

        feature_order,model=self.load_isolation_forest_model(self.model_path)

        while True:
            get_diagnosis_jobs=self.get_diagnosis_jobs()
            self.process_jobs(get_diagnosis_jobs,feature_order=feature_order,model=model)

            time.sleep(self.poll_interval)

if __name__ == "__main__":
    base_api_url=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    model_path="diag_agent_model/iForest/models/isolation_forest_v1.pkl"
    poll_interval=1
    window_size=120
    model_version="isolation_forest_v1"

    diagnosis_agent=DiagnosisAgent(base_api_url=base_api_url,poll_interval=poll_interval,model_path=model_path,window_size=window_size,model_version=model_version)
    diagnosis_agent.run()
        