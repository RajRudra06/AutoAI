# # scheduling_agent

# import time
# import requests
# from datetime import datetime, timezone
# from agents.utils.agent_api_client import get, post
# from helpers.logic.slot_generator import generate_random_service_slot
# from dotenv import load_dotenv
# import os

# load_dotenv()

# BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
# GET_VEHICLES_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"
# GET_BOOKING_FOR_VEHICLE_URL = f"{BASE_API_URL}/api/schedule"
# BOOK_SCHEDULE_URL = f"{BASE_API_URL}/api/schedule/book"
# UPDATE_STATE_URL = f"{BASE_API_URL}/api/schedule/update"
# GET_SERVICE_SLOT = f"{BASE_API_URL}/api/schedule/get_slot"

# POLL_INTERVAL = 15  # seconds

# def run_scheduler():
#     print("[SCHEDULER] Agent started. Monitoring scheduling_required flags...")

#     while True:

#         resp = get(GET_VEHICLES_STATE_URL)
#         vehicles = resp.json().get("vehicles", [])

#         for vehicle in vehicles:
#             vehicle_id = vehicle["vehicle_id"]
#             workflow = vehicle.get("workflow_state", {})
#             flags = workflow.get("flags", {})

#             if workflow.get("current_stage") == "SCHEDULING_COMPLETE":
#                 continue

#             if not flags.get("scheduling_required"):
#                 continue

#             booking_resp = get(
#                 f"{GET_BOOKING_FOR_VEHICLE_URL}/{vehicle_id}"
#             )

#             if booking_resp.status_code == 200 and booking_resp.headers.get("content-type", "").startswith("application/json"):
#                 data = booking_resp.json()
#                 if data.get("data"):
#                     print(f"[SCHEDULER] Booking already exists for {vehicle_id}, skipping")
#                     continue

#             print(f"[SCHEDULER] Creating tentative booking for {vehicle_id}")

#             slot_resp = get(GET_SERVICE_SLOT)
#             slot_to_book = slot_resp.text.strip('"')


#             booking_payload = {
#                 "vehicle_id": vehicle_id,
#                 "slot": slot_to_book, 
#                 "center_id": "SC-01",
#                 "status": "TENTATIVE",
#                 "created_at": datetime.now(timezone.utc).isoformat()
#             }

#             post(
#                 f"{BOOK_SCHEDULE_URL}",
#                 json=booking_payload,
#             )

#             post(
#                 UPDATE_STATE_URL,
#                 json={
#                     "vehicle_id": vehicle_id,
#                     "workflow_state": {
#                         "current_stage": "SCHEDULING_COMPLETE",
#                         "flags": {
#                             "scheduling_required": False,
#                             "engagement_required": True
#                         }
#                     }
#                 },
#             )

#             print(f"[SCHEDULER] Scheduling complete → Engagement required for {vehicle_id}")

#         time.sleep(POLL_INTERVAL)


# if __name__ == "__main__":
#     run_scheduler()

import time 
from agents.utils.agent_api_client import get, post
from datetime import datetime, timezone
import os
from dotenv import load_dotenv


load_dotenv()



class SchedulingAgent:
    def __init__(self,base_api_url:str,poll_interval:int):
        self.base_api_url=base_api_url
        self.poll_interval=poll_interval
    
    def fetch_vehicles_state(self)->dict:
        vehicle_state_url=f"{self.api_base_url}/api/vehicles/state"

        try:
            resp = get(vehicle_state_url)
            vehicles = resp.json().get("vehicles", [])

        except Exception as e:
            print("[MASTER][ERROR] Failed to fetch vehicle state:", e)
            time.sleep(self.poll_interval)
            return []
            
        return vehicles
    
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
    
    def process_vehicles(self,vehicles:dict):
        for vehicle in vehicles:

            lifecycle_gate_check=self.lifecycle_gate_check(vehicle=vehicle)

            if lifecycle_gate_check:
                continue

            get_booking_slot=self.post_booking()

            if get_booking_slot:
                continue


    def post_booking(self,vehicle_id:str)->bool:
        post_booking_api=f"{self.base_api_url}/api/schedule/{vehicle_id}"

        post_booking_resp=get(post_booking_api)

        if post_booking_resp.status_code==200 and post_booking_resp.headers.get("content-type", "").startswith("application/json"):
            data = post_booking_resp.json()
            if data.get("data"):
                    print(f"[SCHEDULER] Booking already exists for {vehicle_id}, skipping")
                    return True
            
        print(f"[SCHEDULER] Creating tentative booking for {vehicle_id}")  

        get_service_slot=self.get_service_slot()

        if get_service_slot:
            return True
        
        booking_payload = {
                        "vehicle_id": vehicle_id,
                        "slot": get_service_slot, 
                        "center_id": "SC-01",
                        "status": "TENTATIVE",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
        
        post_final_booking=self.post_final_booking(booking_payload=booking_payload)

        if not post_final_booking:
            return True

        update_vehicle_state_booking=self.update_vehicle_state(vehicle_id=vehicle_id)

        if not update_vehicle_state_booking:
            return True
    

        print(f"[SCHEDULER] Scheduling complete → Engagement required for {vehicle_id}")

    def update_vehicle_state(self,vehicle_id:str):
        update_state_api=f"{self.base_api_url}/api/schedule/update"

        update_state_resp=post(update_state_api,json={
                    "vehicle_id": vehicle_id,
                    "workflow_state": {
                        "current_stage": "SCHEDULING_COMPLETE",
                        "flags": {
                            "scheduling_required": False,
                            "engagement_required": True
                        }
                    }
                }
                )
        
        if update_state_resp.status_code==200:
            return True
        return False


    def post_final_booking(self,booking_payload:dict):
        book_schedule_api=f"{self.base_api_url}/api/schedule/book"

        post_booking_resp=post(book_schedule_api,json=booking_payload)

        if post_booking_resp.status_code==200:
            return True

        return False

    def get_service_slot(self):
        service_slot_api=f"{self.base_api_url}/api/schedule/get_slot"
        service_slot_resp=get(service_slot_api)
        slot_to_book=service_slot_resp.text.strip('"')

        if service_slot_resp.status_code==200:
            return slot_to_book
        return True

    def lifecycle_gate_check(self,vehicle:dict)->bool:
        vehicle_state_params=self.extract_vehicle_params(vehicle)

        vehicle_id=vehicle_state_params["vehicle_id"]
        workflow_stage=vehicle_state_params["workflow_stage"]
        scheduling_flag=vehicle_state_params["workflow_flags"]["scheduling_required"]

        if workflow_stage=="SCHEDULING_COMPLETE" or not scheduling_flag:
            return True
        
        return False
        


    def run(self):
        
        print("[SCHEDULER] Agent started. Monitoring scheduling_required flags...")

        while True:
            vehicles=self.fetch_vehicles_state()
            self.process_vehicles(vehicles=vehicles)

            time.sleep(self.poll_interval)

if __name__=="__main__":
        base_api_url_val=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
        scheduling_agent=SchedulingAgent(base_api_url=base_api_url_val,poll_interval=15)
        scheduling_agent.run()

