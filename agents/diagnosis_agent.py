# # diagnosis_agent.py
 
# from datetime import datetime, timezone
# import time
# from dotenv import load_dotenv
# import os
# from celery.result import AsyncResult
# from pytz import timezone 

# from agents.utils.agent_api_client import post, get
# from worker_tasks.execution_diagnosis_task import execute_diagnosis_job

# load_dotenv()

# class DiagnosisAgent:
#     def __init__(self,base_api_url:str,poll_interval:int,model_path:str,window_size:int,model_version:str):
#         self.poll_interval=poll_interval
#         self.base_api_url=base_api_url
#         self.model_path=model_path
#         self.window_size=window_size
#         self.model_version=model_version
    
#     def get_diagnosis_jobs(self)->list:
#         get_diagnosis_jobs_api=f"{self.base_api_url}/api/diagnosis/jobs"
#         job_response=get(get_diagnosis_jobs_api)
#         jobs=job_response.json().get("jobs",[])

#         return jobs

#     def extract_vehicle_params(self, vehicle: dict) -> dict:
#         vehicle_id = vehicle["vehicle_id"]
#         workflow = vehicle.get("workflow_state", {})
#         risk_state = vehicle.get("risk_state", {})
#         flags = workflow.get("flags", {})
#         latest = vehicle.get("latest_features", {})
#         previous = vehicle.get("previous_features", {})
#         pipeline = vehicle.get("pipeline_associated") or {} 

#         return {
#             "vehicle_id": vehicle_id,
#             "pipeline_associated": vehicle.get("pipeline_associated"),
#             "celery_task_id": pipeline.get("celery_task_id"),
#             # Workflow
#             "workflow_stage": workflow.get("current_stage"),
#             "workflow_flags": {
#                 "diagnosis_required": flags.get("diagnosis_required", False),
#                 "scheduling_required": flags.get("scheduling_required", False),
#                 "engagement_required": flags.get("engagement_required", False),
#             },

#             # Risk
#             "high_risk_active": risk_state.get("high_risk_active", False),
#             "unresolved_issues": risk_state.get("unresolved_issues", []),

#             # Features (snapshots)
#             "latest_features": latest,
#             "previous_features": previous,

#             "last_updated": vehicle.get("last_updated"),
#             "temp_last_processed_telemetry": vehicle.get("temp_last_processed_telemetry"),
#             "last_processed_telemetry": vehicle.get("last_processed_telemetry"),
#             "latest_feature_associated_telemetryID": vehicle.get("latest_feature_associated_telemetryID"),
#         }
    
#     def process_jobs(self,jobs:list):
#         for job in jobs:
#             job_id=job["_id"]
#             vehicle_id=job["vehicle_id"]

#             vehicle_lifecycle_gate_check=self.lifecycle_gate_check(job_id=job_id,vehicle_id=vehicle_id)

#             if vehicle_lifecycle_gate_check == True:
#                 continue

#             print(f"[DIAGNOSIS DISPATCHER] Delegating job {job_id} for {vehicle_id} to Celery.")

#             self.enqueue_execution_diagnosis_task(job=job,vehicle_id=vehicle_id)

            
#     def enqueue_execution_diagnosis_task(self, job: dict,vehicle_id:str):

#         try:
#             print(f"[DIAGNOSIS SHARD][ENQUEUE] Enqueuing execution diagnosis task for {vehicle_id}")

#             res=execute_diagnosis_job.delay(
#                 job,
#                 self.base_api_url,
#                 self.model_path,
#                 self.window_size,
#                 self.model_version
#             )

#             print(f"[DIAGNOSIS SHARD][ENQUEUE] Task enqueued, task_id=***********************************{res.id}")

#             update_vehicle_state = post(
#             f"{self.api_base_url}/api/vehicles/update",
#             json={
#                 "vehicle_id": vehicle_id,
#                 "pipeline_associated": {
#                     "pipeline_status": "ASSIGNED_BY_DIAGNOSIS_AGENT",
#                     "pipeline_assigned_at": datetime.now(timezone.utc).isoformat(),
#                     "celery_task_id":res.id
#                     }
#                 }
#             )   

#             if update_vehicle_state.status_code != 200:
#                 print(f"[DIAGNOSIS SHARD][ERROR] Failed to update vehicle state for vehicle {vehicle_id}")
#                 return

#             print(f"[DIAGNOSIS SHARD][ENQUEUE] Task queued for {vehicle_id}, task_id={res.id}")

#         except Exception as e:
#             print(f"[DIAGNOSIS SHARD][ERROR] Task queueing failed, rolling back vehicle state: {e}")

#             post(
#                 f"{self.api_base_url}/api/vehicles/update",
#                 json={
#                     "vehicle_id": vehicle_id,
#                     "pipeline_associated": {
#                         "pipeline_status": "TELEMETRY_INITIATED",
#                         "pipeline_assigned_at": "1968-01-01T00:00:00Z"
#                     }
#                 }
#             )

#     def get_vehicle_state(self, vehicle_id: str) -> dict:
#         get_vehicle_state_api = f"{self.base_api_url}/api/vehicles/state/{vehicle_id}"
#         vehicle_resp = get(get_vehicle_state_api)

#         if vehicle_resp.status_code == 200:
#             vehicle_state = vehicle_resp.json()
#             return vehicle_state
        
#         return None
    
#     def skip_job(self,job_id:str)->bool:
#         skip_job_url=f"{self.base_api_url}/api/diagnosis/skip"

#         skip_job=post(skip_job_url,json={"job_id":job_id,"reason":"Lifecycle gate active"})

#         if skip_job.status_code==200:
#             return True
#         return False
        
#     def lifecycle_gate_check(self, job_id: str, vehicle_id: str) -> bool:
#         vehicle_state = self.get_vehicle_state(vehicle_id)

#         # Add None check before using vehicle_state
#         if vehicle_state is None:
#             print(f"[DIAGNOSIS][ERROR] Could not fetch vehicle state for {vehicle_id}")
#             print(vehicle_state)
#             # Skip the job since we can't verify lifecycle state
#             skip_current_vehicle_job = self.skip_job(job_id=job_id)
#             if skip_current_vehicle_job == True:
#                 return True
#             return False
        
#         vehicle_state_params = self.extract_vehicle_params(vehicle=vehicle_state)

#         workflow_stage = vehicle_state_params["workflow_stage"]
#         high_risk = vehicle_state_params["high_risk_active"]
#         last_processed_telemetry = vehicle_state_params["last_processed_telemetry"]
#         latest_feature_associated_telemetryID = vehicle_state_params["latest_feature_associated_telemetryID"]
#         pipeline_status = vehicle_state_params["pipeline_associated"].get("pipeline_status")
#         pipeline_assigned_at=vehicle_state_params["pipeline_associated"].get("pipeline_assigned_at")
#         scheduling_required=vehicle_state_params["workflow_flags"]["scheduling_required"]
#         celery_task_id=vehicle_state_params["celery_task_id"]

#         comparison_datetime = datetime.now(datetime.timezone.utc)
#         now = datetime.now(datetime.timezone.utc)
#         timeout=60

#         if workflow_stage in {"DIAGNOSIS_COMPLETE", "SCHEDULING_COMPLETE", "ENGAGEMENT_COMPLETE"} or high_risk or last_processed_telemetry>=latest_feature_associated_telemetryID or pipeline_status != "ASSIGNED_BY_MASTER_AGENT" or (pipeline_assigned_at and pipeline_assigned_at > comparison_datetime):

#             if(pipeline_status == "ASSIGNED_BY_DIAGNOSIS_AGENT" and pipeline_assigned_at and workflow_stage == "DIAGNOSIS_PENDING" and not scheduling_required and celery_task_id is not None):

#                 if(now-pipeline_assigned_at).total_seconds() > timeout: 
#                     self.reset_stale_vehicle(vehicle=vehicle_state)
#                     print(f"[DIAGNOSIS SHARD {self.shard_id}][GATE] Stale vehicle reset")

#             print(f"[DIAGONSIS SHARD][GATE] Vehicle blocked by lifecycle gate")
#             skip_current_vehicle_job = self.skip_job(job_id=job_id)
#             if skip_current_vehicle_job == True:
#                 return True
                
#         return False
    
#     def reset_stale_vehicle(self, vehicle: dict):
#         vehicle_state_api = f"{self.api_base_url}/api/vehicles/update"
#         vehicle_state_params = self.extract_vehicle_params(vehicle)

#         vehicle_id=vehicle_state_params["vehicle_id"]
#         pipeline_status = vehicle_state_params["pipeline_associated"].get("pipeline_status")
#         pipeline_assigned_at=vehicle_state_params["pipeline_associated"].get("pipeline_assigned_at")
#         scheduling_required=vehicle_state_params["workflow_flags"]["scheduling_required"]
#         celery_task_id=vehicle_state_params["celery_task_id"]

#         if celery_task_id:
#             try:
#                 print(f"[DIAGNOSIS SHARD ][RESET] Revoking task {celery_task_id} for vehicle {vehicle_id}")
#                 AsyncResult(celery_task_id).revoke(terminate=True)
#                 print(f"[DIAGNOSIS SHARD {self.shard_id}][RESET] Task----------------------------------------------------------------------------- {celery_task_id} revoked successfully")
#             except Exception as e:
#                 print(f"[DIAGNOSIS SHARD {self.shard_id}][RESET] Failed to revoke task {celery_task_id}: {e}")
#                 # Continue anyway - still reset the vehicle
#         else:
#             print(f"[DIAGNOSIS SHARD {self.shard_id}][RESET] No task_id found for vehicle {vehicle_id}, skipping revoke")

#         # STEP 2: Reset vehicle state in DB
#         try:
#             update_req = post(
#                 vehicle_state_api,
#                 json={
#                     "vehicle_id": vehicle_id,
#                     "pipeline_associated": {
#                         "pipeline_status": "TELEMETRY_INITIATED",
#                         "pipeline_assigned_at": "1968-01-01T00:00:00Z",
#                         "celery_task_id": None  # ← Clear task ID
#                     },
                    
#                 }
#             )
            
#             if update_req.status_code == 200:
#                 print(f"[DIAGNOSIS SHARD][RESET] Vehicle {vehicle_id} reset successfully -----------------------------------------------------------------------------")
#             else:
#                 print(f"[DIAGNOSIS SHARD][RESET] Failed to reset vehicle {vehicle_id}")

#         except Exception as e:
#             print(f"[DIAGNOSIS SHARD][RESET] Error resetting vehicle {vehicle_id}: {e}")


#     def run(self):
#         print("[DIAGNOSIS] Agent started. Waiting for jobs...")

#         while True:
#             get_diagnosis_jobs=self.get_diagnosis_jobs()
#             self.process_jobs(get_diagnosis_jobs)

#             time.sleep(self.poll_interval)

# if __name__ == "__main__":
#     base_api_url=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
#     model_path="diag_agent_model/iForest/models/isolation_forest_v1.pkl"
#     poll_interval=20
#     window_size=120
#     model_version="isolation_forest_v1"

#     diagnosis_agent=DiagnosisAgent(base_api_url=base_api_url,poll_interval=poll_interval,model_path=model_path,window_size=window_size,model_version=model_version)
#     diagnosis_agent.run()


from datetime import datetime, timezone
import time
from dotenv import load_dotenv
import os
import threading
import traceback
from celery.result import AsyncResult
from pytz import timezone
from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor

from agents.utils.agent_api_client import post, get
from worker_tasks.execution_diagnosis_task import execute_diagnosis_job

load_dotenv()


class DiagnosisAgent:
    def __init__(
        self,
        base_api_url: str,
        poll_interval: int,
        model_path: str,
        window_size: int,
        model_version: str,
        shard_id: int,
        total_shards: int,
        max_threads=10,
    ):
        self.poll_interval = poll_interval
        self.base_api_url = base_api_url
        self.model_path = model_path
        self.window_size = window_size
        self.model_version = model_version
        self.shard_id = shard_id
        self.total_shards = total_shards
        self.max_threads = max_threads

    def get_all_diagnosis_jobs(self) -> list:
        get_diagnosis_jobs_api = f"{self.base_api_url}/api/diagnosis/jobs"
        job_response = get(get_diagnosis_jobs_api)
        jobs = job_response.json().get("jobs", [])
        return jobs

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
            "temp_last_processed_telemetry": vehicle.get(
                "temp_last_processed_telemetry"
            ),
            "last_processed_telemetry": vehicle.get("last_processed_telemetry"),
            "latest_feature_associated_telemetryID": vehicle.get(
                "latest_feature_associated_telemetryID"
            ),
        }

    def cycle(self, jobs_for_my_shard: list):
        print(
            f"[DIAGNOSIS SHARD {self.shard_id}][CYCLE] "
            f"Starting cycle with {len(jobs_for_my_shard)} jobs."
        )
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            executor.map(self.process_single_job, jobs_for_my_shard)
        print(f"[DIAGNOSIS SHARD {self.shard_id}][CYCLE] Cycle complete")

    def process_single_job(self, job: dict):
        try:
            job_id = job["_id"]
            vehicle_id = job["vehicle_id"]
            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][CYCLE] "
                f"Processing job {job_id} for vehicle {vehicle_id}"
            )

            vehicle_lifecycle_gate_check = self.lifecycle_gate_check(
                job_id=job_id, vehicle_id=vehicle_id
            )

            if vehicle_lifecycle_gate_check:
                print(
                    f"[DIAGNOSIS SHARD {self.shard_id}]blocked by [LIFECYCLE-GATE] "
                    f"Job {job_id} for {vehicle_id} skipped by lifecycle gate."
                )
                return

            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][DISPATCHER] "
                f"Delegating job {job_id} for {vehicle_id} to Celery."
            )
            self.enqueue_execution_diagnosis_task(
                job=job, vehicle_id=vehicle_id
            )

        except Exception as e:
            print("\n---!!! UNHANDLED EXCEPTION IN THREAD !!!---")
            print(
                f"--- For Job: {job.get('_id')} for Vehicle "
                f"{job.get('vehicle_id')} on Shard {self.shard_id} ---"
            )
            print(f"--- Error: {e} ---")
            traceback.print_exc()
            print("-------------------------------------------\n")

    def enqueue_execution_diagnosis_task(self, job: dict, vehicle_id: str):
        try:
            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][ENQUEUE] "
                f"Enqueuing execution diagnosis task for {vehicle_id}"
            )

            res = execute_diagnosis_job.delay(
                job,
                self.base_api_url,
                self.model_path,
                self.window_size,
                self.model_version,
            )

            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][ENQUEUE] "
                f"Task enqueued, task_id=***********************************{res.id}"
            )

            update_vehicle_state = post(
                f"{self.base_api_url}/api/vehicles/update",
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "ASSIGNED_BY_DIAGNOSIS_AGENT",
                        "pipeline_assigned_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "celery_task_id": res.id,
                    },
                },
            )

            if update_vehicle_state.status_code != 200:
                print(
                    f"[DIAGNOSIS SHARD {self.shard_id}][ERROR] "
                    f"Failed to update vehicle state for vehicle {vehicle_id}"
                )
                return

            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][ENQUEUE] "
                f"Task queued for {vehicle_id}, task_id={res.id}"
            )

        except Exception as e:
            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][ERROR] "
                f"Task queueing failed, rolling back vehicle state: {e}"
            )

            post(
                f"{self.base_api_url}/api/vehicles/update",
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "TELEMETRY_INITIATED",
                        "pipeline_assigned_at": "1968-01-01T00:00:00Z",
                    },
                },
            )

    def get_vehicle_state(self, vehicle_id: str) -> dict:
        get_vehicle_state_api = (
            f"{self.base_api_url}/api/vehicles/state/{vehicle_id}"
        )
        vehicle_resp = get(get_vehicle_state_api)

        if vehicle_resp.status_code == 200:
            return vehicle_resp.json()

        return None

    def skip_job(self, job_id: str) -> bool:
        skip_job_url = f"{self.base_api_url}/api/diagnosis/skip"

        skip_job = post(
            skip_job_url,
            json={"job_id": job_id, "reason": "Lifecycle gate active"},
        )

        return skip_job.status_code == 200

    def lifecycle_gate_check(self, job_id: str, vehicle_id: str) -> bool:
        vehicle_state = self.get_vehicle_state(vehicle_id)

        if vehicle_state is None:
            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][ERROR] "
                f"Could not fetch vehicle state for {vehicle_id}"
            )
            return self.skip_job(job_id=job_id)

        vehicle_state_params = self.extract_vehicle_params(
            vehicle=vehicle_state
        )

        workflow_stage = vehicle_state_params["workflow_stage"]
        high_risk = vehicle_state_params["high_risk_active"]
        last_processed_telemetry = vehicle_state_params[
            "last_processed_telemetry"
        ]
        latest_feature_associated_telemetryID = vehicle_state_params[
            "latest_feature_associated_telemetryID"
        ]
        pipeline_associated = (
            vehicle_state_params["pipeline_associated"] or {}
        )
        pipeline_status = pipeline_associated.get("pipeline_status")
        pipeline_assigned_at = pipeline_associated.get(
            "pipeline_assigned_at"
        )
        scheduling_required = vehicle_state_params["workflow_flags"][
            "scheduling_required"
        ]
        celery_task_id = vehicle_state_params["celery_task_id"]

        try:
            if isinstance(last_processed_telemetry, str):
                last_processed_telemetry = datetime.fromisoformat(
                    last_processed_telemetry.replace("Z", "+00:00")
                )
            if isinstance(latest_feature_associated_telemetryID, str):
                latest_feature_associated_telemetryID = datetime.fromisoformat(
                    latest_feature_associated_telemetryID.replace(
                        "Z", "+00:00"
                    )
                )
            if isinstance(pipeline_assigned_at, str):
                pipeline_assigned_at = datetime.fromisoformat(
                    pipeline_assigned_at.replace("Z", "+00:00")
                )
        except (ValueError, TypeError) as e:
            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][ERROR] "
                f"Could not parse a timestamp string in lifecycle_gate_check: {e}"
            )
            return True

        comparison_datetime = datetime(1968, 1, 1, tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        timeout = 60

        if (
            workflow_stage
            in {
                "DIAGNOSIS_COMPLETE",
                "SCHEDULING_COMPLETE",
                "ENGAGEMENT_COMPLETE",
            }
            or high_risk
            or (
                last_processed_telemetry
                and latest_feature_associated_telemetryID
                and last_processed_telemetry
                >= latest_feature_associated_telemetryID
            )
            or pipeline_status != "ASSIGNED_BY_MASTER_AGENT"
            or (
                pipeline_assigned_at
                and pipeline_assigned_at > comparison_datetime
            )
        ):
            if (
                pipeline_status == "ASSIGNED_BY_DIAGNOSIS_AGENT"
                and pipeline_assigned_at
                and workflow_stage == "DIAGNOSIS_PENDING"
                and not scheduling_required
                and celery_task_id is not None
            ):
                if (now - pipeline_assigned_at).total_seconds() > timeout:
                    self.reset_stale_vehicle(vehicle=vehicle_state)
                    print(
                        f"[DIAGNOSIS SHARD {self.shard_id}][GATE] "
                        f"Stale vehicle detected trying reset"
                    )

            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][GATE] "
                f"Vehicle blocked by lifecycle gate for job {job_id}"
            )
            return self.skip_job(job_id=job_id)

        return False

    def reset_stale_vehicle(self, vehicle: dict):
        vehicle_state_api = f"{self.base_api_url}/api/vehicles/update"
        vehicle_state_params = self.extract_vehicle_params(vehicle)

        vehicle_id = vehicle_state_params["vehicle_id"]
        celery_task_id = vehicle_state_params["celery_task_id"]

        if celery_task_id:
            try:
                print(
                    f"[DIAGNOSIS SHARD {self.shard_id}][RESET] "
                    f"Revoking task {celery_task_id} for vehicle {vehicle_id}"
                )
                AsyncResult(celery_task_id).revoke(terminate=True)
                print(
                    f"[DIAGNOSIS SHARD {self.shard_id}][RESET] "
                    f"Task {celery_task_id} revoked successfully"
                )
            except Exception as e:
                print(
                    f"[DIAGNOSIS SHARD {self.shard_id}][RESET] "
                    f"Failed to revoke task {celery_task_id}: {e}"
                )
        else:
            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][RESET] "
                f"No task_id found for vehicle {vehicle_id}, skipping revoke"
            )

        try:
            update_req = post(
                vehicle_state_api,
                json={
                    "vehicle_id": vehicle_id,
                    "pipeline_associated": {
                        "pipeline_status": "TELEMETRY_INITIATED",
                        "pipeline_assigned_at": datetime(1968, 1, 1, tzinfo=timezone.utc),
                        "celery_task_id": None,
                    },
                    "temp_last_processed_telemetry":datetime(1969, 1, 1, tzinfo=timezone.utc),
                    "last_processed_telemetry":datetime(1970, 1, 1, tzinfo=timezone.utc),
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
                },
            )

            if update_req.status_code == 200:
                print(
                    f"[DIAGNOSIS SHARD {self.shard_id}][RESET] "
                    f"Vehicle {vehicle_id} reset successfully"
                )
            else:
                print(
                    f"[DIAGNOSIS SHARD {self.shard_id}][RESET] "
                    f"Failed to reset vehicle {vehicle_id}"
                )

        except Exception as e:
            print(
                f"[DIAGNOSIS SHARD {self.shard_id}][RESET] "
                f"Error resetting vehicle {vehicle_id}: {e}"
            )


def run_shard_cycle(work_packet: tuple):
    (
        shard_id,
        total_shards,
        base_api_url,
        poll_interval,
        model_path,
        window_size,
        model_version,
        max_threads,
        jobs_for_this_shard,
    ) = work_packet

    agent = DiagnosisAgent(
        base_api_url=base_api_url,
        poll_interval=poll_interval,
        model_path=model_path,
        window_size=window_size,
        model_version=model_version,
        shard_id=shard_id,
        total_shards=total_shards,
        max_threads=max_threads,
    )

    if jobs_for_this_shard:
        agent.cycle(jobs_for_this_shard)


def orchestrator_main():
    base_api_url = os.getenv(
        "BACKEND_API_URL", "http://127.0.0.1:8000"
    )
    model_path = (
        "diag_agent_model/iForest/models/isolation_forest_v1.pkl"
    )
    poll_interval = int(
        os.getenv("DIAGNOSIS_POLL_INTERVAL", "20")
    )
    window_size = int(os.getenv("DIAGNOSIS_WINDOW_SIZE", "120"))
    model_version = os.getenv(
        "DIAGNOSIS_MODEL_VERSION", "isolation_forest_v1"
    )
    total_shards = int(
        os.getenv("DIAGNOSIS_TOTAL_SHARDS", cpu_count())
    )
    max_threads = int(os.getenv("DIAGNOSIS_MAX_THREADS", "10"))

    print(
        f"[DIAGNOSIS ORCHESTRATOR] Initializing Process Pool "
        f"with {total_shards} shards..."
    )

    with Pool(processes=total_shards) as pool:
        while True:
            print("[DIAGNOSIS ORCHESTRATOR] Starting new cycle...")

            temp_agent = DiagnosisAgent(
                base_api_url=base_api_url,
                poll_interval=poll_interval,
                model_path=model_path,
                window_size=window_size,
                model_version=model_version,
                shard_id=0,
                total_shards=1,
            )
            all_diagnosis_jobs = temp_agent.get_all_diagnosis_jobs()

            if not all_diagnosis_jobs:
                print(
                    "[DIAGNOSIS ORCHESTRATOR] No diagnosis jobs found. Sleeping."
                )
                time.sleep(poll_interval)
                continue

            workloads = [[] for _ in range(total_shards)]
            for job in all_diagnosis_jobs:
                target_shard = hash(job["vehicle_id"]) % total_shards
                workloads[target_shard].append(job)

            work_packets = [
                (
                    shard_id,
                    total_shards,
                    base_api_url,
                    poll_interval,
                    model_path,
                    window_size,
                    model_version,
                    max_threads,
                    job_list,
                )
                for shard_id, job_list in enumerate(workloads)
            ]

            pool.map(run_shard_cycle, work_packets)

            print(
                f"[DIAGNOSIS ORCHESTRATOR] Cycle complete. "
                f"Sleeping for {poll_interval} seconds."
            )
            time.sleep(poll_interval)


if __name__ == "__main__":
    try:
        orchestrator_main()
    except KeyboardInterrupt:
        print(
            "\n[DIAGNOSIS ORCHESTRATOR] Shutdown signal received. Exiting."
        )