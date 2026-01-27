import time 
import os
from dotenv import load_dotenv
from agents.utils.agent_api_client import get, post
from helpers.logic.health_gate import needs_diagnosis
from datetime import datetime
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
        workflow = vehicle.get("workflow_state") or {}
        risk_state = vehicle.get("risk_state") or {}
        flags = workflow.get("flags") or {}
        latest = vehicle.get("latest_features") or {}
        previous = vehicle.get("previous_features") or {}

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

            "last_updated": vehicle.get("last_updated"),
            "last_processed_telemetry": vehicle.get("last_processed_telemetry"),
            "latest_feature_associated_telemetryID": vehicle.get(
                "latest_feature_associated_telemetryID"
            ),
        }
    
    def process_vehicle(self,vehicle: dict):
        

        vehicle_state_params=self.extract_vehicle_params(vehicle)

        check_skip_vehicle=self.lifecycle_gate(workflow_stage=vehicle_state_params["workflow_stage"] ,high_risk_active=vehicle_state_params["high_risk_active"],last_processed_telemetry=vehicle_state_params["last_processed_telemetry"],feature_associated_telemetryID=vehicle_state_params["latest_feature_associated_telemetryID"])

        return check_skip_vehicle
        
    
    def lifecycle_gate(self,workflow_stage: str,high_risk_active:bool,last_processed_telemetry:datetime,feature_associated_telemetryID:datetime) -> bool:

        if workflow_stage in {
            "DIAGNOSIS_PENDING",
            "DIAGNOSIS_COMPLETE",
            "SCHEDULING_COMPLETE",
            "ENGAGEMENT_COMPLETE"
            
        } or high_risk_active or last_processed_telemetry>=feature_associated_telemetryID:
            return True
        
        return False
        
if __name__ == "__main__":
    base_api_url_val=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    master_agent=MasterAgent(api_base_url_val=base_api_url_val,poll_interval_val=1)
    master_agent.run()


