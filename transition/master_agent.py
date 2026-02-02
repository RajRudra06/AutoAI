import time
import os
from dotenv import load_dotenv
from agents.utils.agent_api_client import get, post
from helpers.logic.health_gate import needs_diagnosis
from datetime import datetime, timezone
# NEW: Import the celery task
from tasks_celery.diagnosis_task import queue_diagnosis_job 

load_dotenv()

class MasterAgent:

    def __init__(self, api_base_url_val, poll_interval_val):
        self.poll_interval = poll_interval_val
        self.api_base_url = api_base_url_val
        print(f"[MASTER][INIT] api_base_url={self.api_base_url}, poll_interval={self.poll_interval}")

    def fetch_vehicle_state(self):
        vehicle_state_url = f"{self.api_base_url}/api/vehicles/state"
        print(f"[MASTER][FETCH] Fetching vehicle states from {vehicle_state_url}")

        try:
            resp = get(vehicle_state_url)
            vehicles = resp.json().get("vehicles", [])
            print(f"[MASTER][FETCH] Retrieved {len(vehicles)} vehicles")
        except Exception as e:
            print("[MASTER][ERROR] Failed to fetch vehicle state:", e)
            time.sleep(self.poll_interval)
            return []

        return vehicles

    def diagnosis_check(self, vehicle):
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        print(f"[MASTER][DIAG-CHECK] Checking vehicle {vehicle_state_params['vehicle_id']}")

        diagnosis_required = vehicle_state_params["workflow_flags"]["diagnosis_required"]

        if diagnosis_required:
            print(f"[MASTER][DIAG-CHECK] Skipped — diagnosis already required")
            return None

        should_trigger, reasons = needs_diagnosis(
            telemetry=vehicle_state_params["latest_features"],
            previous_telemetry=vehicle_state_params["previous_features"]
        )

        print(
            f"[MASTER][DIAG-CHECK] {vehicle_state_params['vehicle_id']} | "
            f"trigger={should_trigger} | "
            f"reasons={reasons} | "
            f"stage={vehicle_state_params['workflow_stage']} | "
            f"flags={vehicle_state_params['workflow_flags']}"
        )

        if not should_trigger:
            print(f"[MASTER][DIAG-CHECK] No diagnosis triggered")
            return None

        print(f"[MASTER][DIAG-CHECK] Diagnosis SHOULD be triggered")
        return {"reasons": reasons, "should_trigger": should_trigger}

    def cycle(self):
        print("[MASTER][CYCLE] Starting cycle")

        vehicles = self.fetch_vehicle_state()

        for vehicle in vehicles:
            print(f"[MASTER][CYCLE] Processing vehicle {vehicle.get('vehicle_id')}")

            # MODIFIED: Get vehicle_state_params once to use later
            vehicle_state_params = self.extract_vehicle_params(vehicle)
            vehicle_skip_check = self.process_vehicle(vehicle, vehicle_state_params) # Pass params

            if vehicle_skip_check:
                print(f"[MASTER][CYCLE] Skipped by lifecycle gate")
                continue

            diagnosis_result = self.diagnosis_check(vehicle)

            if diagnosis_result is None:
                print(f"[MASTER][CYCLE] Diagnosis not required")
                continue

            # --- MODIFIED: Call Celery task instead of local method ---
            print(f"[MASTER][QUEUE] Delegating diagnosis job for {vehicle_state_params['vehicle_id']} to Celery")
            queue_diagnosis_job.delay(
                vehicle_id=vehicle_state_params["vehicle_id"],
                features_snapshot=vehicle_state_params["latest_features"],
                trigger_reasons=diagnosis_result["reasons"],
                latest_feature_associated_telemetryID=vehicle_state_params["latest_feature_associated_telemetryID"]
            )
            # REMOVED: time.sleep(10) as the call is now non-blocking

        print("[MASTER][CYCLE] Cycle complete")

    # --- REMOVED: put_diagnosis_job method ---

    def run(self):
        print("[MASTER] Agent started. Observing vehicle_state...")

        while True:
            self.cycle()
            time.sleep(self.poll_interval)

    def extract_vehicle_params(self, vehicle: dict) -> dict:
        print(f"[MASTER][EXTRACT] Extracting vehicle params")

        vehicle_id = vehicle["vehicle_id"]
        workflow = vehicle.get("workflow_state") or {}
        risk_state = vehicle.get("risk_state") or {}
        flags = workflow.get("flags") or {}
        latest = vehicle.get("latest_features") or {}
        previous = vehicle.get("previous_features") or {}

        return {
            "vehicle_id": vehicle_id,
            "pipeline_associated": vehicle.get("pipeline_associated"),
            "workflow_stage": workflow.get("current_stage"),
            "workflow_flags": {
                "diagnosis_required": flags.get("diagnosis_required", False),
                "scheduling_required": flags.get("scheduling_required", False),
                "engagement_required": flags.get("engagement_required", False),
            },

            "high_risk_active": risk_state.get("high_risk_active", False),
            "unresolved_issues": risk_state.get("unresolved_issues", []),

            "latest_features": latest,
            "previous_features": previous,

            "last_updated": vehicle.get("last_updated"),
            "temp_last_processed_telemetry": vehicle.get("temp_last_processed_telemetry"),
            "last_processed_telemetry": vehicle.get("last_processed_telemetry"),
            "latest_feature_associated_telemetryID":
                vehicle.get("latest_feature_associated_telemetryID"),
        }

    # MODIFIED: process_vehicle now accepts params to avoid re-extraction
    def process_vehicle(self, vehicle: dict, vehicle_state_params: dict):
        print(
            f"[MASTER][GATE] Vehicle={vehicle_state_params['vehicle_id']} | "
            f"stage={vehicle_state_params['workflow_stage']} | "
            f"risk={vehicle_state_params['high_risk_active']} | "
            f"last_processed={vehicle_state_params['last_processed_telemetry']} | "
            f"latest={vehicle_state_params['latest_feature_associated_telemetryID']}"
        )

        check_skip_vehicle = self.lifecycle_gate(
            workflow_stage=vehicle_state_params["workflow_stage"],
            high_risk_active=vehicle_state_params["high_risk_active"],
            last_processed_telemetry=vehicle_state_params["last_processed_telemetry"],
            latest_feature_associated_telemetryID=
                vehicle_state_params["latest_feature_associated_telemetryID"],
            pipeline_associated=vehicle_state_params["pipeline_associated"] or {},
            vehicle=vehicle
        )

        return check_skip_vehicle

    def lifecycle_gate(
        self,
        workflow_stage: str,
        high_risk_active: bool,
        last_processed_telemetry: datetime,
        latest_feature_associated_telemetryID: datetime,
        pipeline_associated: dict,vehicle: dict
    ) -> bool:

        pipeline_status = pipeline_associated.get("pipeline_status", "UNKNOWN")
        pipeline_assigned_at = pipeline_associated.get("pipeline_assigned_at")
        now=datetime.now(timezone.utc)
        timeout=3600

        if (
            workflow_stage in {
                "DIAGNOSIS_PENDING",
                "DIAGNOSIS_COMPLETE",
                "SCHEDULING_COMPLETE",
                "ENGAGEMENT_COMPLETE"
            }
            or high_risk_active
            or last_processed_telemetry >= latest_feature_associated_telemetryID or pipeline_status != "TELEMETRY_INITIATED" or pipeline_assigned_at > datetime(1968, 1, 1, tzinfo=timezone.utc)
            ):
            print("[MASTER][GATE] Vehicle blocked by lifecycle gate")

            # This logic might be better as its own celery task too
            if pipeline_status != "TELEMETRY_INITIATED" and (now - pipeline_assigned_at) > timeout:
                self.reset_stale_vehicle(vehicle=vehicle)
                print("[MASTER][GATE] Stale vehicle reset")
                
            return True

        print("[MASTER][GATE] Vehicle allowed to proceed")
        return False
    
    def reset_stale_vehicle(self, vehicle: dict):
        vehicle_state_api=f"{self.api_base_url}/api/vehicles/update"
        vehicle_state_params=self.extract_vehicle_params(vehicle)

        update_req=post(vehicle_state_api,json={
                    "vehicle_id": vehicle_state_params["vehicle_id"],
                     "pipeline_associated":{
                    "pipeline_status":"TELEMETRY_INITIATED",
                    "pipeline_assigned_at":"1968-01-01T00:00:00Z"
                }
                })

if __name__ == "__main__":
    base_api_url_val = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    master_agent = MasterAgent(
        api_base_url_val=base_api_url_val,
        poll_interval_val=20
    )
    master_agent.run()
