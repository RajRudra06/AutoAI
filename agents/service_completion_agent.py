import time
import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timezone
from agents.utils.agent_api_client import get, post

load_dotenv()
# new to new branch hello 
class ServiceCompletionAgent:
    def __init__(self,base_api_url:str,poll_interval:int):
        self.base_api_url=base_api_url
        self.poll_interval=poll_interval

    def fetch_vehicle_state(self)->dict:
        vehicle_state_url=f"{self.base_api_url}/api/vehicles/state"

        try:
            resp = get(vehicle_state_url)
            vehicles = resp.json().get("vehicles", [])

        except Exception as e:
            print("[SERVICE COMPLETION][ERROR] Failed to fetch vehicle state:", e)
            time.sleep(self.poll_interval)
            return []
            
        return vehicles
    
    def process_vehicles(self,vehicles:dict):
        
        for vehicle in vehicles:
            vehicle_id=vehicle["vehicle_id"]
            stage = vehicle["workflow_state"]["current_stage"]
            temp_last_processed_telemetry=vehicle["temp_last_processed_telemetry"]
            lifecycle_gate_check=self.lifecycle_gate_check(vehicle_id=vehicle_id,stage=stage)

            if lifecycle_gate_check:
                continue

            print(f"[SERVICE] Completing service for {vehicle_id}")

            update_vehicle_schedule=self.update_vehicle_schedule(vehicle_id=vehicle_id)

            if update_vehicle_schedule:
                continue

            update_vehicle_state=self.update_vehicle_state(vehicle_id=vehicle_id,temp_last_processed_telemetry=temp_last_processed_telemetry)

            if update_vehicle_state:
                continue

            print(f"[SERVICE] Completing logging for {vehicle_id}")

            post_feedback_log=self.post_feedback_log(vehicle_id=vehicle_id)

            if post_feedback_log:
                continue

            print(f"[SERVICE] Lifecycle closed for {vehicle_id}")
    
    def post_feedback_log(self,vehicle_id:str)->bool:
        feedback_log_api=f"{self.base_api_url}/api/feedback/log"

        post_feedback_log_resp=post(feedback_log_api,json={
                    "vehicle_id": vehicle_id,
                    "message": "Service completed successfully",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

        if post_feedback_log_resp.status_code==200:
            return False
        return True


    def update_vehicle_state(self,vehicle_id:str,temp_last_processed_telemetry:datetime)->bool:
        update_vehicle_state_api=f"{self.base_api_url}/api/vehicles/update"

        update_vehicle_state_resp=post(update_vehicle_state_api,json={
                    "vehicle_id": vehicle_id,
                    # put the timestamp of the telemetry that caused the master to diagonse
                    "last_processed_telemetry":temp_last_processed_telemetry,
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

        if update_vehicle_state_resp.status_code==200:
            return False
        return True
         

    def update_vehicle_schedule(self,vehicle_id:str)->bool:

        update_schedule_api=f"{self.base_api_url}/api/schedule/update"

        update_vehicle_schedule_resp=post(update_schedule_api,json={
            "vehicle_id":vehicle_id,
            "status":"COMPLETED",
            "completed_at":datetime.now(timezone.utc).isoformat()
        })

        if update_vehicle_schedule_resp.status_code==200:
            return False
        return True

    def lifecycle_gate_check(self,vehicle_id:str,stage:str)->bool:

        if stage != "ENGAGEMENT_COMPLETE":
            return True
        
        booking_status=self.get_booking_status(vehicle_id=vehicle_id)
        if not booking_status:
            return True
        
        if booking_status.json().get("data").get("status")=="COMPLETED":
            return True
        
        return False
    
    def get_booking_status(self,vehicle_id:str)->bool:
        booking_status_api=f"{self.base_api_url}/api/schedule/{vehicle_id}"

        booking_status_resp=get(booking_status_api)

        if booking_status_resp.status_code==200 and booking_status_resp:
            return booking_status_resp
        
        return False
        
    def run(self):
        print("[SERVICE COMPLETION] Agent started. Waiting for service completion...")

        while True:
            get_vehicles_state=self.fetch_vehicle_state()
            self.process_vehicles(vehicles=get_vehicles_state)

            time.sleep(self.poll_interval)

if __name__=="__main__":
        base_api_url=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
        service_completion_agent=ServiceCompletionAgent(base_api_url=base_api_url,poll_interval=1)
        service_completion_agent.run()
