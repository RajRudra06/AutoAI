
import time
from datetime import datetime, timezone
import os
import threading
import traceback
from celery.result import AsyncResult
from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor

from agents.utils.agent_api_client import post, get
from worker_tasks.scheduling_tasks import execute_scheduling_job

class SchedulingAgent:
    def __init__(self, base_api_url: str, poll_interval: int, shard_id: int, total_shards: int, max_threads=10):
        self.base_api_url = base_api_url
        self.poll_interval = poll_interval
        self.shard_id = shard_id
        self.total_shards = total_shards
        self.max_threads = max_threads

    def fetch_all_vehicles_globally(self) -> list:
        
        vehicle_state_url = f"{self.base_api_url}/api/vehicles/state"
        try:
            resp = get(vehicle_state_url)
            return resp.json().get("vehicles", [])
        except Exception as e:
            print(f"[SCHEDULING ORCHESTRATOR][ERROR] Failed to fetch all vehicle states: {e}")
            return []

    def extract_vehicle_params(self, vehicle: dict) -> dict:
        vehicle_id = vehicle["vehicle_id"]
        workflow = vehicle.get("workflow_state", {})
        risk_state = vehicle.get("risk_state", {})
        flags = workflow.get("flags", {})
        latest = vehicle.get("latest_features", {})
        previous = vehicle.get("previous_features", {})
        pipeline = vehicle.get("pipeline_associated") or {}

        return {
            "vehicle_id": vehicle_id,
            "pipeline_associated": vehicle.get("pipeline_associated"),
            "celery_task_id": pipeline.get("celery_task_id"),
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
            "latest_feature_associated_telemetryID": vehicle.get("latest_feature_associated_telemetryID"),
             "last_processed_telemetry": vehicle.get("last_processed_telemetry")
        }

    def cycle(self, vehicles_for_my_shard: list):
        print(f"[SCHEDULING SHARD {self.shard_id}][CYCLE] Starting cycle with {len(vehicles_for_my_shard)} vehicles.")
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            executor.map(self.process_single_vehicle, vehicles_for_my_shard)
        print(f"[SCHEDULING SHARD {self.shard_id}][CYCLE] Cycle complete")

    def process_single_vehicle(self, vehicle: dict):
        try:
            vehicle_id = vehicle["vehicle_id"]
            print(f"[SCHEDULING SHARD {self.shard_id}][CYCLE] Processing vehicle {vehicle_id}")

            vehicle_lifecycle_gate_check = self.lifecycle_gate_check(vehicle=vehicle)

            if vehicle_lifecycle_gate_check:
                print(f"[SCHEDULING SHARD {self.shard_id}]blocked by [LIFECYCLE-GATE] Vehicle {vehicle_id} skipped by lifecycle gate.")
                return

            print(f"[SCHEDULING SHARD {self.shard_id}][DISPATCHER] Delegating scheduling for {vehicle_id} to Celery.")
            self.enqueue_scheduling_task(vehicle=vehicle)

        except Exception as e:

            print(f"--- For Vehicle: {vehicle.get('vehicle_id')} on Shard {self.shard_id} ---")
            print(f"--- Error: {e} ---")
            traceback.print_exc()
            print(f"-------------------------------------------")

    def enqueue_scheduling_task(self, vehicle: dict):
        vehicle_state_params = self.extract_vehicle_params(vehicle)
        vehicle_id = vehicle_state_params["vehicle_id"]

        try:
            print(f"[SCHEDULING SHARD {self.shard_id}][ENQUEUE] Enqueuing scheduling task for {vehicle_id}")

            res = execute_scheduling_job.delay(
                vehicle_id=vehicle_id,
                base_api_url=self.base_api_url
            )

            print(f"[SCHEDULING SHARD {self.shard_id}][ENQUEUE] Task enqueued, task_id=***********************************{res.id}")

            update_vehicle_state = post(
                f"{self.base_api_url}/api/vehicles/update",
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "ASSIGNED_BY_SCHEDULING_AGENT", 
                        "pipeline_assigned_at": datetime.now(timezone.utc).isoformat(),
                        "celery_task_id": res.id
                    }
                }
            )

            if update_vehicle_state.status_code != 200:
                print(f"[SCHEDULING SHARD {self.shard_id}][ERROR] Failed to update vehicle state for vehicle {vehicle_id}")
                return

            print(f"[SCHEDULING SHARD {self.shard_id}][ENQUEUE] Task queued for {vehicle_id}, task_id={res.id}")

        except Exception as e:
            print(f"[SCHEDULING SHARD {self.shard_id}][ERROR] Task queueing failed, rolling back vehicle state: {e}")
            post(
                f"{self.base_api_url}/api/vehicles/update",
               json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "TELEMETRY_INITIATED",
                        "pipeline_assigned_at": datetime(1968, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "celery_task_id": None,
                    },
                    "temp_last_processed_telemetry":datetime(1969, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "last_processed_telemetry":datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat()    ,
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
                }
            )

    def lifecycle_gate_check(self, vehicle: dict) -> bool:
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        vehicle_id = vehicle_state_params["vehicle_id"]
        workflow_stage = vehicle_state_params["workflow_stage"]
        scheduling_flag = vehicle_state_params["workflow_flags"]["scheduling_required"]
        engagement_flag=vehicle_state_params["workflow_flags"]["engagement_required"]
        pipeline_status = vehicle_state_params["pipeline_associated"].get("pipeline_status")
        pipeline_assigned_at = vehicle_state_params["pipeline_associated"].get("pipeline_assigned_at")
        celery_task_id = vehicle_state_params["celery_task_id"]
        last_processed_telemetry = vehicle_state_params["last_processed_telemetry"]
        latest_feature_associated_telemetryID = vehicle_state_params["latest_feature_associated_telemetryID"]
        high_risk_active = vehicle_state_params["high_risk_active"]


        try:
            if isinstance(last_processed_telemetry, str):
                last_processed_telemetry = datetime.fromisoformat(last_processed_telemetry.replace('Z', '+00:00'))
            if isinstance(latest_feature_associated_telemetryID, str):
                latest_feature_associated_telemetryID = datetime.fromisoformat(latest_feature_associated_telemetryID.replace('Z', '+00:00'))
            if isinstance(pipeline_assigned_at, str):
                pipeline_assigned_at = datetime.fromisoformat(pipeline_assigned_at.replace('Z', '+00:00'))
        except (ValueError, TypeError) as e:
            print(f"[ERROR][SHARD {self.shard_id}] Could not parse a timestamp string in lifecycle_gate: {e}")
            return True

        now = datetime.now(timezone.utc) 
        timeout = 60 

        if (
            workflow_stage in {"SCHEDULING_COMPLETE", "ENGAGEMENT_COMPLETE"}
            or last_processed_telemetry>= latest_feature_associated_telemetryID
            or (pipeline_assigned_at and pipeline_status != "ASSIGNED_BY_DIAGNOSIS_AGENT")
           
        ):

            if (
                pipeline_status == "ASSIGNED_BY_SCHEDULING_AGENT"
                and pipeline_assigned_at
                and workflow_stage == "DIAGNOSIS_COMPLETE" 
                and not engagement_flag 
                and celery_task_id is not None
            ):

                if (now - pipeline_assigned_at).total_seconds() > timeout:
                    self.reset_stale_vehicle(vehicle=vehicle)

                    print(f"[SCHEDULING SHARD {self.shard_id}][GATE] Stale vehicle detected and reset for {vehicle_id}")


            print(f"[SCHEDULING SHARD {self.shard_id}][GATE] Vehicle {vehicle_id} blocked by lifecycle gate.")

            return True 

        return False

    def reset_stale_vehicle(self, vehicle: dict):
        vehicle_state_api = f"{self.base_api_url}/api/vehicles/update"
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        vehicle_id = vehicle_state_params["vehicle_id"]
        celery_task_id = vehicle_state_params["celery_task_id"]

        if celery_task_id:
            try:
                print(f"[SCHEDULING SHARD {self.shard_id}][RESET] Revoking task {celery_task_id} for vehicle {vehicle_id}")
                AsyncResult(celery_task_id).revoke(terminate=True)
                print(f"[SCHEDULING SHARD {self.shard_id}][RESET] Task {celery_task_id} revoked successfully")
            except Exception as e:
                print(f"[SCHEDULING SHARD {self.shard_id}][RESET] Failed to revoke task {celery_task_id}: {e}")
        else:
            print(f"[SCHEDULING SHARD {self.shard_id}][RESET] No task_id found for vehicle {vehicle_id}, skipping revoke")

        try:
            update_req = post(
                vehicle_state_api,
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "TELEMETRY_INITIATED",
                        "pipeline_assigned_at": datetime(1968, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "celery_task_id": None,
                    },
                    "temp_last_processed_telemetry":datetime(1969, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "last_processed_telemetry":datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat()    ,
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
                }
            )

            if update_req.status_code == 200:
                print(f"[SCHEDULING SHARD {self.shard_id}][RESET] Vehicle {vehicle_id} reset successfully")
            else:
                print(f"[SCHEDULING SHARD {self.shard_id}][RESET] Failed to reset vehicle {vehicle_id}")

        except Exception as e:
            print(f"[SCHEDULING SHARD {self.shard_id}][RESET] Error resetting vehicle {vehicle_id}: {e}")

def run_shard_cycle(work_packet: tuple):
    shard_id, total_shards, base_api_url, poll_interval, max_threads, vehicles_for_this_shard = work_packet

    agent = SchedulingAgent(
        base_api_url=base_api_url,
        poll_interval=poll_interval,
        shard_id=shard_id,
        total_shards=total_shards,
        max_threads=max_threads
    )

    if vehicles_for_this_shard:
        agent.cycle(vehicles_for_this_shard)

def orchestrator_main():
    base_api_url = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    poll_interval = int(os.getenv("SCHEDULING_POLL_INTERVAL", "20"))
    total_shards = int(os.getenv("SCHEDULING_TOTAL_SHARDS", cpu_count()))
    max_threads = int(os.getenv("SCHEDULING_MAX_THREADS", "10"))

    print(f"[SCHEDULING ORCHESTRATOR] Initializing Process Pool with {total_shards} shards...")
    with Pool(processes=total_shards) as pool:
        while True:
            print("[SCHEDULING ORCHESTRATOR] Starting new cycle...")

            temp_agent = SchedulingAgent(
                base_api_url=base_api_url,
                poll_interval=poll_interval,
                shard_id=0,
                total_shards=1
            )
            all_vehicles = temp_agent.fetch_all_vehicles_globally() 

            if not all_vehicles:
                print("[SCHEDULING ORCHESTRATOR] No vehicles found. Sleeping.")
                time.sleep(poll_interval)
                continue

            workloads = [[] for _ in range(total_shards)]
            for vehicle in all_vehicles:
                target_shard = hash(vehicle['vehicle_id']) % total_shards
                workloads[target_shard].append(vehicle)

            work_packets = [
                (shard_id, total_shards, base_api_url, poll_interval, max_threads, vehicle_list)
                for shard_id, vehicle_list in enumerate(workloads)
            ]

            pool.map(run_shard_cycle, work_packets)

            print(f"[SCHEDULING ORCHESTRATOR] Cycle complete. Sleeping for {poll_interval} seconds.")
            time.sleep(poll_interval)

if __name__ == "__main__":
    try:
        orchestrator_main()
    except KeyboardInterrupt:
        print("[SCHEDULING ORCHESTRATOR] Shutdown signal received. Exiting.")