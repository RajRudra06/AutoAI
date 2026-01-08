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
