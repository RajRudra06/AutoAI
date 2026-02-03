
import time
import os
from dotenv import load_dotenv
from agents.utils.agent_api_client import get, post
from helpers.logic.health_gate import needs_diagnosis
from datetime import datetime, timezone
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor

# Import Celery task
from tasks.diagnosis_tasks import run_diagnosis

load_dotenv()

class MasterAgent:

    def __init__(self, api_base_url_val, poll_interval_val, shard_id, total_shards, max_threads=10):
        self.poll_interval = poll_interval_val
        self.api_base_url = api_base_url_val
        self.shard_id = shard_id
        self.total_shards = total_shards
        self.max_threads = max_threads
        print(f"[MASTER SHARD {shard_id}][INIT] api_base_url={self.api_base_url}, poll_interval={self.poll_interval}")
        print(f"[MASTER SHARD {shard_id}][INIT] Shard {shard_id} of {total_shards}, max_threads={max_threads}")

    def owns_vehicle(self, vehicle_id: str) -> bool:
        """NEW: Deterministic sharding"""
        return hash(vehicle_id) % self.total_shards == self.shard_id

    def fetch_vehicle_state(self):
        vehicle_state_url = f"{self.api_base_url}/api/vehicles/state"
        print(f"[MASTER SHARD {self.shard_id}][FETCH] Fetching vehicle states from {vehicle_state_url}")

        try:
            resp = get(vehicle_state_url)
            all_vehicles = resp.json().get("vehicles", [])
            
            # Filter to only my shard
            vehicles = [v for v in all_vehicles if self.owns_vehicle(v["vehicle_id"])]
            
            print(f"[MASTER SHARD {self.shard_id}][FETCH] Total: {len(all_vehicles)}, My shard: {len(vehicles)}")
        except Exception as e:
            print(f"[MASTER SHARD {self.shard_id}][ERROR] Failed to fetch vehicle state:", e)
            time.sleep(self.poll_interval)
            return []

        return vehicles

    def diagnosis_check(self, vehicle):
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        print(f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] Checking vehicle {vehicle_state_params['vehicle_id']}")

        diagnosis_required = vehicle_state_params["workflow_flags"]["diagnosis_required"]

        if diagnosis_required:
            print(f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] Skipped — diagnosis already required")
            return None

        should_trigger, reasons = needs_diagnosis(
            telemetry=vehicle_state_params["latest_features"],
            previous_telemetry=vehicle_state_params["previous_features"]
        )

        print(
            f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] {vehicle_state_params['vehicle_id']} | "
            f"trigger={should_trigger} | "
            f"reasons={reasons} | "
            f"stage={vehicle_state_params['workflow_stage']} | "
            f"flags={vehicle_state_params['workflow_flags']}"
        )

        if not should_trigger:
            print(f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] No diagnosis triggered")
            return None

        print(f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] Diagnosis SHOULD be triggered")
        return {"reasons": reasons, "should_trigger": should_trigger}

    def cycle(self):
        """NEW: Now processes vehicles in parallel using ThreadPoolExecutor"""
        print(f"[MASTER SHARD {self.shard_id}][CYCLE] Starting cycle")

        vehicles = self.fetch_vehicle_state()

        # NEW: Process vehicles concurrently using ThreadPool
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            executor.map(self.process_single_vehicle, vehicles)

        print(f"[MASTER SHARD {self.shard_id}][CYCLE] Cycle complete")

    def process_single_vehicle(self, vehicle):
        """NEW: Process one vehicle (runs in thread)"""
        print(f"[MASTER SHARD {self.shard_id}][CYCLE] Processing vehicle {vehicle.get('vehicle_id')}")

        vehicle_skip_check = self.process_vehicle(vehicle)

        if vehicle_skip_check:
            print(f"[MASTER SHARD {self.shard_id}][CYCLE] Skipped by lifecycle gate")
            return

        diagnosis_result = self.diagnosis_check(vehicle)

        if diagnosis_result is None:
            print(f"[MASTER SHARD {self.shard_id}][CYCLE] Diagnosis not required")
            return

        self.enqueue_diagnosis_task(vehicle, diagnosis_result["reasons"])

        time.sleep(10)

    def enqueue_diagnosis_task(self, vehicle: dict, reasons: dict):
        """NEW: Enqueue Celery task for diagnosis execution"""
        vehicle_state_params = self.extract_vehicle_params(vehicle)
        vehicle_id = vehicle_state_params["vehicle_id"]

        try:
            print(f"[MASTER SHARD {self.shard_id}][ENQUEUE] Enqueuing diagnosis task for {vehicle_id}")

            # Enqueue Celery task (non-blocking)
            run_diagnosis.delay(
                vehicle_id=vehicle_id,
                features_snapshot=vehicle_state_params["latest_features"],
                trigger_reasons=reasons,
                api_base_url=self.api_base_url,
                latest_feature_associated_telemetryID=vehicle_state_params["latest_feature_associated_telemetryID"]
            )

            print(f"[MASTER SHARD {self.shard_id}][ENQUEUE] Task queued for {vehicle_id}")

        except Exception as e:
            print(f"[MASTER SHARD {self.shard_id}][ERROR] Failed to enqueue {vehicle_id}: {e}")

    def run(self):
        print(f"[MASTER SHARD {self.shard_id}] Agent started. Observing vehicle_state...")

        while True:
            self.cycle()
            time.sleep(self.poll_interval)

    def extract_vehicle_params(self, vehicle: dict) -> dict:
        print(f"[MASTER SHARD {self.shard_id}][EXTRACT] Extracting vehicle params")

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

    def process_vehicle(self, vehicle: dict):
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        print(
            f"[MASTER SHARD {self.shard_id}][GATE] Vehicle={vehicle_state_params['vehicle_id']} | "
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
        pipeline_associated: dict,
        vehicle: dict
    ) -> bool:

        pipeline_status = pipeline_associated.get("pipeline_status", "UNKNOWN")
        pipeline_assigned_at = pipeline_associated.get("pipeline_assigned_at")
        now = datetime.now(timezone.utc)
        timeout = 3600

        if (
            workflow_stage in {
                "DIAGNOSIS_PENDING",
                "DIAGNOSIS_COMPLETE",
                "SCHEDULING_COMPLETE",
                "ENGAGEMENT_COMPLETE"
            }
            or high_risk_active
            or last_processed_telemetry >= latest_feature_associated_telemetryID 
            or pipeline_status != "TELEMETRY_INITIATED" 
            or (pipeline_assigned_at and pipeline_assigned_at > datetime(1968, 1, 1, tzinfo=timezone.utc))
        ):
            print(f"[MASTER SHARD {self.shard_id}][GATE] Vehicle blocked by lifecycle gate")

            if pipeline_status != "TELEMETRY_INITIATED" and pipeline_assigned_at:
                try:
                    if isinstance(pipeline_assigned_at, str):
                        assigned_at = datetime.fromisoformat(pipeline_assigned_at.replace('Z', '+00:00'))
                    else:
                        assigned_at = pipeline_assigned_at
                    
                    if (now - assigned_at).total_seconds() > timeout:
                        self.reset_stale_vehicle(vehicle=vehicle)
                        print(f"[MASTER SHARD {self.shard_id}][GATE] Stale vehicle reset")
                except Exception as e:
                    print(f"[MASTER SHARD {self.shard_id}][ERROR] Stale check failed: {e}")
                
            return True

        print(f"[MASTER SHARD {self.shard_id}][GATE] Vehicle allowed to proceed")
        return False
    
    def reset_stale_vehicle(self, vehicle: dict):
        vehicle_state_api = f"{self.api_base_url}/api/vehicles/update"
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        update_req = post(
            vehicle_state_api,
            json={
                "vehicle_id": vehicle_state_params["vehicle_id"],
                "pipeline_associated": {
                    "pipeline_status": "TELEMETRY_INITIATED",
                    "pipeline_assigned_at": "1968-01-01T00:00:00Z"
                }
            }
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NEW: MULTIPROCESSING ORCHESTRATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_shard(shard_id, total_shards, base_api_url, poll_interval, max_threads):
    """Run a single shard in its own process"""
    master_agent = MasterAgent(
        api_base_url_val=base_api_url,
        poll_interval_val=poll_interval,
        shard_id=shard_id,
        total_shards=total_shards,
        max_threads=max_threads
    )
    master_agent.run()


def start_all_shards(total_shards, base_api_url, poll_interval, max_threads):
    """NEW: Spawn multiple shard processes"""
    print(f"[ORCHESTRATOR] Starting {total_shards} shards...")
    
    processes = []
    for shard_id in range(total_shards):
        p = Process(
            target=run_shard,
            args=(shard_id, total_shards, base_api_url, poll_interval, max_threads)
        )
        p.start()
        processes.append(p)
        print(f"[ORCHESTRATOR] Shard {shard_id} started (PID: {p.pid})")
    
    # Wait for all shards (they run forever)
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[ORCHESTRATOR] Shutting down all shards...")
        for p in processes:
            p.terminate()
        print("[ORCHESTRATOR] All shards terminated")


if __name__ == "__main__":
    # Configuration
    base_api_url_val = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    total_shards = int(os.getenv("TOTAL_SHARDS", "3"))
    poll_interval = int(os.getenv("POLL_INTERVAL", "20"))
    max_threads = int(os.getenv("MAX_THREADS", "10"))
    
    # Start all shards
    start_all_shards(
        total_shards=total_shards,
        base_api_url=base_api_url_val,
        poll_interval=poll_interval,
        max_threads=max_threads
    )