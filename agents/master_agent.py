import time 
import os
from dotenv import load_dotenv
from agents.utils.agent_api_client import get, post
from helpers.logic.health_gate import needs_diagnosis

load_dotenv()

class MasterAgent:

    def __init__(self, api_base_url_val, poll_interval_val):
        self.poll_interval=poll_interval_val
        self.api_base_url=api_base_url_val

    def fetch_vehicle_state(self):
        vehicle_state_url=f"{self.api_base_url}/api/vehicles/state"

        try:
            resp = get(vehicle_state_url)
            vehicles = resp.json().get("vehicles", [])

        except Exception as e:
            print("[MASTER][ERROR] Failed to fetch vehicle state:", e)
            time.sleep(self.poll_interval)
            return []
            
        return vehicles
    
    def diagnosis_check(self,vehicle):

        vehicle_state_params = self.extract_vehicle_params(vehicle)

        diagnosis_required = vehicle_state_params["workflow_flags"]["diagnosis_required"]

        if diagnosis_required:
            return None

        should_trigger, reasons = needs_diagnosis(
            telemetry=vehicle_state_params["latest_features"],
            previous_telemetry=vehicle_state_params["previous_features"]
        )

        print(
            f"[MASTER][CHECK] {vehicle_state_params['vehicle_id']} | "
            f"trigger={should_trigger} | "
            f"reasons={reasons} | "
            f"stage={vehicle_state_params["workflow_stage"]} | "
            f"flags={vehicle_state_params["workflow_flags"]}"
        )

        if not should_trigger:
            return None


        return {"reasons":reasons,"should_trigger":should_trigger}
    
    def cycle(self):

        vehicles=self.fetch_vehicle_state()
        
        for vehicle in vehicles:
            vehicle_skip_check=self.process_vehicle(vehicle)

            if vehicle_skip_check:
                continue
            
            diagnosis_result=self.diagnosis_check(vehicle)

            if diagnosis_result is None:
                continue

            self.put_diagnosis_job(vehicle,diagnosis_result["reasons"])
            
        
    def put_diagnosis_job(self,vehicle:dict,reasons:dict):
        
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        try:
            post(
                f"{self.api_base_url}/api/diagnosis/queue",
                json={
                    "vehicle_id": vehicle_state_params["vehicle_id"],
                    "features_snapshot": vehicle_state_params["latest_features"],
                    "trigger_reasons": reasons
                }
            )
            print(f"[MASTER][QUEUED] {vehicle_state_params["vehicle_id"]} → DIAGNOSIS_PENDING")

        except Exception as e:
            print(f"[MASTER][ERROR] Failed to queue {vehicle_state_params["vehicle_id"]}: {e}")

    
    def run(self):
        print("[MASTER] Agent started. Observing vehicle_state...")

        while True:
            self.cycle()
            time.sleep(self.poll_interval)

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
    
    def process_vehicle(self,vehicle: dict):
        

        vehicle_state_params=self.extract_vehicle_params(vehicle)

        check_skip_vehicle=self.lifecycle_gate(workflow_stage=vehicle_state_params["workflow_stage"] ,high_risk_active=vehicle_state_params["high_risk_active"])

        return check_skip_vehicle
        
    
    def lifecycle_gate(self,workflow_stage: str,high_risk_active:bool) -> bool:
        return (
        workflow_stage in {
            "DIAGNOSIS_PENDING",
            "DIAGNOSIS_COMPLETE",
            "SCHEDULING",
            "IN_SERVICE",
        }
        or high_risk_active
    )
        
if __name__ == "__main__":
    base_api_url_val=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    master_agent=MasterAgent(api_base_url_val=base_api_url_val,poll_interval_val=15)
    master_agent.run()


     # diagnosis_agent

# import time
# import joblib
# import numpy as np
# from datetime import datetime, timezone
# from dotenv import load_dotenv
# import os

# from backend.db.connection import db
# from helpers.logic.get_feature_name import get_feature_names
# from helpers.logic.risk_scoring import transform_scores_to_risk
# from agents.utils.agent_api_client import post, get

# load_dotenv()

# POLL_INTERVAL = 10  # seconds

# MODEL_PATH = "diag_agent_model/iForest/models/isolation_forest_v1.pkl"
# MODEL_VERSION = "isolation_forest_v1"
# FEATURE_VERSION = "v1"
# WINDOW_SIZE = 120

# BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
# GET_DIAGNOSIS_JOBS_API_URL = f"{BASE_API_URL}/api/diagnosis/jobs"
# START_JOB_URL = f"{BASE_API_URL}/api/diagnosis/start"
# COMPLETE_JOB_URL = f"{BASE_API_URL}/api/diagnosis/complete"
# SKIP_JOB_URL = f"{BASE_API_URL}/api/diagnosis/skip"
# FAIL_JOB_URL = f"{BASE_API_URL}/api/diagnosis/fail"
# GET_VEHICLE_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"


# print("[DIAGNOSIS] Loading ML model...")
# model = joblib.load(MODEL_PATH)
# FEATURE_ORDER = get_feature_names()
# print("[DIAGNOSIS] Model loaded.")


# def run_diagnosis():
#     print("[DIAGNOSIS] Agent started. Waiting for jobs...")

#     while True:

#         resp = get(GET_DIAGNOSIS_JOBS_API_URL)
#         jobs = resp.json().get("jobs", [])

#         for job in jobs:
#             job_id = job["_id"]
#             vehicle_id = job["vehicle_id"]
#             features_dict = job["features_snapshot"]
#             unresolved_issues = job.get("trigger_reasons", [])

#             # ================================
#             # 🚫 LIFECYCLE GATE (NEW)
#             # ================================
#             vehicle_resp = get(
#                 f"{GET_VEHICLE_STATE_URL}/{vehicle_id}"
#             )

#             if vehicle_resp.status_code == 200:
#                 state = vehicle_resp.json()
#                 stage = state.get("workflow_state", {}).get("current_stage")
#                 high_risk = state.get("risk_state", {}).get("high_risk_active", False)

#                 if stage in {"DIAGNOSIS_COMPLETE", "SCHEDULING", "IN_SERVICE"} or high_risk:
#                     post(
#                         SKIP_JOB_URL,
#                         json={
#                             "job_id": job_id,
#                             "reason": "Lifecycle gate active"
#                         }
#                     )
#                     continue

#             # Mark job in progress
#             try:
#                 post(START_JOB_URL, json={"job_id": job_id})
#             except Exception:
#                 continue  # someone else took it

#             print(f"[DIAGNOSIS] Processing {vehicle_id}")

#             try:
#                 X = np.array([[features_dict[f] for f in FEATURE_ORDER]])

#                 anomaly_scores = model.score_samples(X)
#                 risk_scores = transform_scores_to_risk(anomaly_scores)

#                 anomaly_score = float(anomaly_scores[0])
#                 risk_score = float(risk_scores[0])
#                 is_anomaly = bool(model.predict(X)[0] == -1)

#                 risk_level = "HIGH" if is_anomaly else "LOW"
#                 unresolved_issues = job.get("trigger_reasons", [])

#                 payload = {
#                     "job_id": job_id,
#                     "vehicle_id": vehicle_id,
#                     "anomaly_score": anomaly_score,
#                     "risk_score": risk_score,
#                     "risk_level": risk_level,
#                     "features_snapshot": features_dict,
#                     "unresolved_issues": unresolved_issues,
#                     "feature_version": FEATURE_VERSION,
#                     "window_size": WINDOW_SIZE,
#                     "model_version": MODEL_VERSION
#                 }

#                 post(COMPLETE_JOB_URL, json=payload)

#                 print(
#                     f"[DIAGNOSIS][DONE] {vehicle_id} | "
#                     f"risk={risk_level} | score={risk_score:.3f}"
#                 )

#             except Exception as e:
#                 post(
#                     FAIL_JOB_URL,
#                     json={
#                         "job_id": job_id,
#                         "error": str(e)
#                     }
#                 )
#                 print(f"[DIAGNOSIS][ERROR] {vehicle_id}: {e}")

#         time.sleep(POLL_INTERVAL)


# if __name__ == "__main__":
#     run_diagnosis()

# diagnosis_agent