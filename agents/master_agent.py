# master_agent.py

from celery.result import AsyncResult 
import time
import os
import threading
import traceback
from dotenv import load_dotenv
from agents.utils.agent_api_client import get, post
from helpers.logic.health_gate import needs_diagnosis
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count  
from concurrent.futures import ThreadPoolExecutor

from worker_tasks.diagnosis_tasks import run_diagnosis

load_dotenv()

class MasterAgent:

    def __init__(self, api_base_url_val, shard_id, total_shards, max_threads=10):
        self.api_base_url = api_base_url_val
        self.shard_id = shard_id
        self.total_shards = total_shards
        self.max_threads = max_threads

    def log_activity(self, vehicle_id: str, action: str, status: str, summary: str, **details):
        try:
            post(
                f"{self.api_base_url}/api/activity/log",
                json={
                    "vehicle_id": vehicle_id,
                    "source_type": "agent",
                    "source_name": "master_agent",
                    "action": action,
                    "status": status,
                    "summary": summary,
                    "details": {
                        "shard_id": self.shard_id,
                        **details,
                    },
                },
            )
        except Exception:
            pass
        
    def diagnosis_check(self, vehicle):
        vehicle_state_params = self.extract_vehicle_params(vehicle)
        vehicle_id = vehicle_state_params["vehicle_id"]
        print(f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] Checking vehicle {vehicle_state_params['vehicle_id']}")
        diagnosis_required = vehicle_state_params["workflow_flags"]["diagnosis_required"]
        if diagnosis_required:
            print(f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] Skipped — diagnosis already required")
            self.log_activity(
                vehicle_id=vehicle_id,
                action="master_gate_diagnosis_already_required",
                status="skipped",
                summary="Master gate skipped because diagnosis was already required.",
                workflow_stage=vehicle_state_params["workflow_stage"],
            )
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
            self.log_activity(
                vehicle_id=vehicle_id,
                action="master_gate_no_diagnosis",
                status="info",
                summary="Master gate evaluated telemetry and did not trigger diagnosis.",
                reasons=reasons,
            )
            return None
        print(f"[MASTER SHARD {self.shard_id}][DIAG-CHECK] Diagnosis SHOULD triggered")
        self.log_activity(
            vehicle_id=vehicle_id,
            action="master_gate_diagnosis_triggered",
            status="success",
            summary="Master gate triggered diagnosis enqueue.",
            reasons=reasons,
        )
        return {"reasons": reasons, "should_trigger": should_trigger}

    def cycle(self, vehicles_for_my_shard: list):
        print(f"[MASTER SHARD {self.shard_id}][CYCLE] Starting cycle with {len(vehicles_for_my_shard)} vehicles.")
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            executor.map(self.process_single_vehicle, vehicles_for_my_shard)
        print(f"[MASTER SHARD {self.shard_id}][CYCLE] Cycle complete")

    def process_single_vehicle(self, vehicle):
        try:
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
            time.sleep(2)
        except Exception as e:
            print(f"\n---!!! UNHANDLED EXCEPTION IN THREAD !!!---")
            print(f"--- For Vehicle: {vehicle.get('vehicle_id')} on Shard {self.shard_id} ---")
            print(f"--- Error: {e} ---")
            traceback.print_exc()
            print(f"-------------------------------------------\n")

    def enqueue_diagnosis_task(self, vehicle: dict, reasons: dict):
        vehicle_state_params = self.extract_vehicle_params(vehicle)
        vehicle_id = vehicle_state_params["vehicle_id"]
        thread_id = threading.get_ident()
        try:
            print(f"[MASTER SHARD {self.shard_id}][ENQUEUE] Enqueuing diagnosis task for {vehicle_id}")

            res = run_diagnosis.delay(
                vehicle_id=vehicle_id,
                master_shard_id=self.shard_id,
                thread_id=thread_id,
                features_snapshot=vehicle_state_params["latest_features"],
                trigger_reasons=reasons,
                api_base_url=self.api_base_url,
                latest_feature_associated_telemetryID=vehicle_state_params["latest_feature_associated_telemetryID"]
            )

            print(f"[MASTER SHARD {self.shard_id}][ENQUEUE] Task enqueued, task_id=***********************************{res.id}")

            update_vehicle_state = post(
                f"{self.api_base_url}/api/vehicles/update",
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "ASSIGNED_BY_MASTER_AGENT",
                        "pipeline_assigned_at": datetime.now(timezone.utc).isoformat(),
                        "celery_task_id":res.id
                    }
                }
            )
            
            if update_vehicle_state.status_code != 200:
                print(f"[MASTER SHARD {self.shard_id}][ERROR] Failed to update vehicle state for vehicle {vehicle_id}")
                return

            print(f"[MASTER SHARD {self.shard_id}][ENQUEUE] Task queued for {vehicle_id}, task_id={res.id}")
            self.log_activity(
                vehicle_id=vehicle_id,
                action="master_enqueue_diagnosis",
                status="success",
                summary="Diagnosis task enqueued by master agent.",
                celery_task_id=res.id,
            )

        except Exception as e:
            print(f"[MASTER SHARD {self.shard_id}][ERROR] Task queueing failed, rolling back vehicle state: {e}")
            self.log_activity(
                vehicle_id=vehicle_id,
                action="master_enqueue_diagnosis",
                status="failed",
                summary="Master agent failed to enqueue diagnosis task.",
                error=str(e),
            )

            post(
                f"{self.api_base_url}/api/vehicles/update",
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

    def extract_vehicle_params(self, vehicle: dict) -> dict:
        vehicle_id = vehicle["vehicle_id"]
        workflow = vehicle.get("workflow_state") or {}
        risk_state = vehicle.get("risk_state") or {}
        flags = workflow.get("flags") or {}
        latest = vehicle.get("latest_features") or {}
        previous = vehicle.get("previous_features") or {}
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
            latest_feature_associated_telemetryID=vehicle_state_params["latest_feature_associated_telemetryID"],
            pipeline_associated=vehicle_state_params["pipeline_associated"] or {},
            vehicle=vehicle
        )
        print(f"[MASTER SHARD {self.shard_id}][GATE] check_skip_vehicle={check_skip_vehicle}")
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
        vehicle_state_params = self.extract_vehicle_params(vehicle)
        diagnosis_required = vehicle_state_params["workflow_flags"]["diagnosis_required"]
        timeout = 60 # 2 mins

        celery_task_id = vehicle_state_params["celery_task_id"]
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
        comparison_datetime = datetime(1968, 1, 1, tzinfo=timezone.utc)
        if (
            workflow_stage in {"DIAGNOSIS_PENDING", "DIAGNOSIS_COMPLETE", "SCHEDULING_COMPLETE", "ENGAGEMENT_COMPLETE"}
            or high_risk_active
            or (latest_feature_associated_telemetryID is None)
            or (last_processed_telemetry is not None and latest_feature_associated_telemetryID is not None and last_processed_telemetry >= latest_feature_associated_telemetryID)
            or (pipeline_assigned_at and pipeline_status != "TELEMETRY_INITIATED")
        ):
            print(f"[MASTER SHARD {self.shard_id}][GATE] Vehicle blocked by lifecycle gate")

            if (pipeline_status == "ASSIGNED_BY_MASTER_AGENT" and pipeline_assigned_at and workflow_stage == "IDLE" and not diagnosis_required and celery_task_id is not None) :
                if (now - pipeline_assigned_at).total_seconds() > timeout:
                    self.reset_stale_vehicle(vehicle=vehicle)
                    print(f"[MASTER SHARD {self.shard_id}][GATE] Stale vehicle reset")
                    
            return True
        print(f"[MASTER SHARD {self.shard_id}][GATE] Vehicle allowed to proceed")
        return False
    
    def reset_stale_vehicle(self, vehicle: dict):
        vehicle_state_api = f"{self.api_base_url}/api/vehicles/update"
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        vehicle_id=vehicle_state_params["vehicle_id"]
        celery_task_id=vehicle_state_params["celery_task_id"]

        if celery_task_id:
            try:
                print(f"[MASTER SHARD {self.shard_id}][RESET] Revoking task {celery_task_id} for vehicle {vehicle_id}")
                AsyncResult(celery_task_id).revoke(terminate=True)
                print(f"[MASTER SHARD {self.shard_id}][RESET] Task----------------------------------------------------------------------------- {celery_task_id} revoked successfully")
            except Exception as e:
                print(f"[MASTER SHARD {self.shard_id}][RESET] Failed to revoke task {celery_task_id}: {e}")
                
        else:
            print(f"[MASTER SHARD {self.shard_id}][RESET] No task_id found for vehicle {vehicle_id}, skipping revoke")
        
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
                print(f"[MASTER SHARD {self.shard_id}][RESET] Vehicle {vehicle_id} reset successfully -----------------------------------------------------------------------------")
            else:
                print(f"[MASTER SHARD {self.shard_id}][RESET] Failed to reset vehicle {vehicle_id}")

        except Exception as e:
            print(f"[MASTER SHARD {self.shard_id}][RESET] Error resetting vehicle {vehicle_id}: {e}")

def fetch_all_vehicles_globally(api_url: str) -> list:
    vehicle_state_url = f"{api_url}/api/vehicles/state"
    print(f"[ORCHESTRATOR][FETCH] Fetching all vehicle states from {vehicle_state_url}")
    try:
        resp = get(vehicle_state_url)
        return resp.json().get("vehicles", [])
    except Exception as e:
        print(f"[ORCHESTRATOR][ERROR] Failed to fetch all vehicle states: {e}")
        return []

def run_shard_cycle(work_packet: tuple):
   
    shard_id, total_shards, api_url, max_threads, vehicles_for_this_shard = work_packet
    
    agent = MasterAgent(
        api_base_url_val=api_url,
        shard_id=shard_id,
        total_shards=total_shards,
        max_threads=max_threads
    )
    
    if vehicles_for_this_shard:
        agent.cycle(vehicles_for_this_shard)

def orchestrator_main():
    base_api_url_val = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    total_shards = int(os.getenv("TOTAL_SHARDS", cpu_count()))
    poll_interval = int(os.getenv("POLL_INTERVAL", "20"))
    max_threads = int(os.getenv("MAX_THREADS", "10"))

    print(f"[ORCHESTRATOR] Initializing Process Pool with {total_shards} shards...")
    with Pool(processes=total_shards) as pool:
        while True:
            print("[ORCHESTRATOR] Starting new cycle...")
            
            all_vehicles = fetch_all_vehicles_globally(base_api_url_val)
            
            if not all_vehicles:
                print("[ORCHESTRATOR] No vehicles found. Sleeping.")
                time.sleep(poll_interval)
                continue

            workloads = [[] for _ in range(total_shards)]
            for vehicle in all_vehicles:
                target_shard = hash(vehicle['vehicle_id']) % total_shards
                workloads[target_shard].append(vehicle)

            work_packets = [
                (shard_id, total_shards, base_api_url_val, max_threads, vehicle_list)
                for shard_id, vehicle_list in enumerate(workloads)
            ]

            pool.map(run_shard_cycle, work_packets)

            print(f"[ORCHESTRATOR] Cycle complete. Sleeping for {poll_interval} seconds.")
            time.sleep(poll_interval)

if __name__ == "__main__":
    try:
        orchestrator_main()
    except KeyboardInterrupt:
        print("\n[ORCHESTRATOR] Shutdown signal received. Exiting.")