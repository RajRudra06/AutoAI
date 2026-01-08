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
        vehicle_state_url=f"{self.base_api_url}/api/vehicles/state"

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
            vehicle_state_params=self.extract_vehicle_params(vehicle)

            vehicle_id=vehicle_state_params["vehicle_id"]

            lifecycle_gate_check=self.lifecycle_gate_check(vehicle=vehicle)

            if lifecycle_gate_check:
                continue

            get_booking_slot=self.post_booking(vehicle_id=vehicle_id)

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

        if not get_service_slot:
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
        return None

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
        base_api_url=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
        scheduling_agent=SchedulingAgent(base_api_url=base_api_url,poll_interval=15)
        scheduling_agent.run()

