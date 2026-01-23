import time
import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timezone
from agents.utils.agent_api_client import get, post

load_dotenv()

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

            lifecycle_gate_check=self.lifecycle_gate_check(vehicle_id=vehicle_id,stage=stage)

            if lifecycle_gate_check:
                continue

            print(f"[SERVICE] Completing service for {vehicle_id}")

            update_vehicle_schedule=self.update_vehicle_schedule(vehicle_id=vehicle_id)

            if update_vehicle_schedule:
                continue

            update_vehicle_state=self.update_vehicle_state(vehicle_id=vehicle_id)

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


    def update_vehicle_state(self,vehicle_id:str)->bool:
        update_vehicle_state_api=f"{self.base_api_url}/api/vehicles/update"

        update_vehicle_state_resp=post(update_vehicle_state_api,json={
                    "vehicle_id": vehicle_id,
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

# class ServiceCompletionAgent:
#     def __init__(self, base_api_url: str, poll_interval: int):
#         self.base_api_url = base_api_url
#         self.poll_interval = poll_interval

#     def fetch_vehicle_state(self) -> dict:
#         vehicle_state_url = f"{self.base_api_url}/api/vehicles/state"
#         print("[SERVICE][FETCH] Fetching vehicle states...")

#         try:
#             resp = get(vehicle_state_url)
#             vehicles = resp.json().get("vehicles", [])
#             print(f"[SERVICE][FETCH] Vehicles received: {len(vehicles)}")

#         except Exception as e:
#             print("[SERVICE][ERROR] Failed to fetch vehicle state:", e)
#             time.sleep(self.poll_interval)
#             return []

#         return vehicles

#     def process_vehicles(self, vehicles: dict):
#         print(f"[SERVICE][PROCESS] Processing {len(vehicles)} vehicles")

#         for vehicle in vehicles:
#             vehicle_id = vehicle["vehicle_id"]
#             stage = vehicle["workflow_state"]["current_stage"]

#             print(f"\n[SERVICE][VEHICLE] {vehicle_id}")
#             print(f"  └─ Current stage: {stage}")

#             lifecycle_gate_check = self.lifecycle_gate_check(
#                 vehicle_id=vehicle_id, stage=stage
#             )

#             if lifecycle_gate_check:
#                 print("  ⏭ Skipped by lifecycle gate")
#                 continue

#             print("  ▶ Updating schedule → COMPLETED")
#             update_vehicle_schedule = self.update_vehicle_schedule(vehicle_id=vehicle_id)

#             if update_vehicle_schedule:
#                 print("  ❌ Schedule update failed, skipping")
#                 continue

#             print("  ✔ Schedule updated")

#             print("  ▶ Updating vehicle state → IDLE")
#             update_vehicle_state = self.update_vehicle_state(vehicle_id=vehicle_id)

#             if update_vehicle_state:
#                 print("  ❌ Vehicle state update failed, skipping")
#                 continue

#             print("  ✔ Vehicle state updated")

#             print("  ▶ Posting feedback log")
#             post_feedback_log = self.post_feedback_log(vehicle_id=vehicle_id)

#             if post_feedback_log:
#                 print("  ❌ Feedback logging failed, skipping")
#                 continue

#             print(f"[SERVICE] ✅ Lifecycle closed for {vehicle_id}")

#     def post_feedback_log(self, vehicle_id: str) -> bool:
#         print(f"    [FEEDBACK] Logging feedback for {vehicle_id}")

#         feedback_log_api = f"{self.base_api_url}/api/feedback/log"
#         resp = post(
#             feedback_log_api,
#             json={
#                 "vehicle_id": vehicle_id,
#                 "message": "Service completed successfully",
#                 "created_at": datetime.now(timezone.utc).isoformat()
#             }
#         )

#         print(f"    [FEEDBACK] Status code: {resp.status_code}")
#         return resp.status_code != 200

#     def update_vehicle_state(self, vehicle_id: str) -> bool:
#         print(f"    [STATE] Updating vehicle state for {vehicle_id}")

#         update_vehicle_state_api = f"{self.base_api_url}/api/vehicles/update"
#         resp = post(
#             update_vehicle_state_api,
#             json={
#                 "vehicle_id": vehicle_id,
#                 "workflow_state": {
#                     "current_stage": "IDLE",
#                     "flags": {
#                         "diagnosis_required": False,
#                         "scheduling_required": False,
#                         "engagement_required": False
#                     }
#                 },
#                 "risk_state": {
#                     "high_risk_active": False,
#                     "unresolved_issues": []
#                 }
#             }
#         )

#         print(f"    [STATE] Status code: {resp.status_code}")
#         return resp.status_code != 200

#     def update_vehicle_schedule(self, vehicle_id: str) -> bool:
#         print(f"    [SCHEDULE] Completing schedule for {vehicle_id}")

#         update_schedule_api = f"{self.base_api_url}/api/schedule/update"
#         resp = post(
#             update_schedule_api,
#             json={
#                 "vehicle_id": vehicle_id,
#                 "status": "COMPLETED",
#                 "completed_at": datetime.now(timezone.utc).isoformat()
#             }
#         )

#         print(f"    [SCHEDULE] Status code: {resp.status_code}")
#         return resp.status_code != 200

#     def lifecycle_gate_check(self, vehicle_id: str, stage: str) -> bool:
#         print("  ▶ Running lifecycle gate check")

#         if stage != "ENGAGEMENT_COMPLETE":
#             print("    ⛔ Blocked: stage != ENGAGEMENT_COMPLETE")
#             return True

#         booking_status = self.get_booking_status(vehicle_id=vehicle_id)

#         if not booking_status:
#             print("    ⛔ Blocked: booking not found")
#             return True

#         status = booking_status.json().get("data", {}).get("status")
#         print(f"    [BOOKING] Current booking status: {status}")

#         if status == "COMPLETED":
#             print("    ⛔ Blocked: booking already completed")
#             return True

#         print("    ✔ Lifecycle gate passed")
#         return False

#     def get_booking_status(self, vehicle_id: str):
#         print(f"    [BOOKING] Fetching booking for {vehicle_id}")

#         booking_status_api = f"{self.base_api_url}/api/schedule/{vehicle_id}"
#         resp = get(booking_status_api)

#         print(resp)

#         if resp.status_code == 200:
#             print("    [BOOKING] Booking fetched successfully")
#             return resp

#         print("    [BOOKING] Booking fetch failed")
#         return False

#     def run(self):
#         print("[SERVICE COMPLETION] Agent started.")
#         print(f"[SERVICE COMPLETION] Poll interval: {self.poll_interval}s")
#         print(f"[SERVICE COMPLETION] Backend URL: {self.base_api_url}\n")

#         while True:
#             vehicles = self.fetch_vehicle_state()
#             self.process_vehicles(vehicles=vehicles)

#             print(f"\n[SERVICE COMPLETION] Sleeping for {self.poll_interval}s...\n")
#         time.sleep(self.poll_interval)

if __name__=="__main__":
        base_api_url=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
        service_completion_agent=ServiceCompletionAgent(base_api_url=base_api_url,poll_interval=1)
        service_completion_agent.run()
