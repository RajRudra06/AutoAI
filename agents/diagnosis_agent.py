import time
import joblib
import numpy as np
from datetime import datetime, timezone

from backend.db.connection import db
from helpers.logic.get_feature_name import get_feature_names  
from helpers.logic.risk_scoring import transform_scores_to_risk     

POLL_INTERVAL = 10  # seconds

MODEL_PATH = "diag_agent_model/iForest/models/isolation_forest_v1.pkl"
MODEL_VERSION = "isolation_forest_v1"
FEATURE_VERSION = "v1"
WINDOW_SIZE = 120

print("[DIAGNOSIS] Loading ML model...")
model = joblib.load(MODEL_PATH)
FEATURE_ORDER = get_feature_names() 
print("[DIAGNOSIS] Model loaded.")


def run_diagnosis():
    print("[DIAGNOSIS] Agent started. Waiting for jobs...")

    while True:
        # Only pick jobs that are not already being processed
        jobs = list(db.diagnosis_jobs.find({"status": "PENDING"}))

        for job in jobs:
            job_id = job["_id"]
            vehicle_id = job["vehicle_id"]
            features_dict = job["features_snapshot"]

            db.diagnosis_jobs.update_one(
                {"_id": job_id, "status": "PENDING"},
                {
                    "$set": {
                        "status": "IN_PROGRESS",
                        "started_at": datetime.now(timezone.utc)
                    }
                }
            )

            print(f"[DIAGNOSIS] Processing {vehicle_id}")

            try:
             
                X = np.array([[features_dict[f] for f in FEATURE_ORDER]])

                
                anomaly_scores = model.score_samples(X)
                risk_scores = transform_scores_to_risk(anomaly_scores)

                anomaly_score = float(anomaly_scores[0])
                risk_score = float(risk_scores[0])
                is_anomaly = bool(model.predict(X)[0] == -1)

                risk_level = "HIGH" if is_anomaly else "LOW"
                unresolved_issues = job.get("trigger_reasons", [])

                db.predictions.insert_one({
                    "vehicle_id": vehicle_id,
                    "anomaly_score": anomaly_score,
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "features_snapshot": features_dict,
                    "feature_version": FEATURE_VERSION,
                    "window_size": WINDOW_SIZE,
                    "model_version": MODEL_VERSION,
                    "created_at": datetime.now(timezone.utc)
                })

                db.vehicle_state.update_one(
                    {"vehicle_id": vehicle_id},
                    {
                        "$set": {
                            "workflow_state.current_stage": "DIAGNOSIS_COMPLETE",
                            "workflow_state.flags.diagnosis_required": False,
                            "workflow_state.flags.scheduling_required": True,

                            "risk_state.high_risk_active": is_anomaly,
                            "risk_state.unresolved_issues": unresolved_issues,

                            "last_updated": datetime.now(timezone.utc)
                        }
                    }
                )

                db.diagnosis_jobs.update_one(
                    {"_id": job_id},
                    {
                        "$set": {
                            "status": "COMPLETED",
                            "completed_at": datetime.now(timezone.utc)
                        }
                    }
                )

                print(
                    f"[DIAGNOSIS][DONE] {vehicle_id} | "
                    f"risk={risk_level} | score={risk_score:.3f}"
                )

            except Exception as e:
    
                db.diagnosis_jobs.update_one(
                    {"_id": job_id},
                    {
                        "$set": {
                            "status": "FAILED",
                            "error": str(e),
                            "failed_at": datetime.now(timezone.utc)
                        }
                    }
                )
                print(f"[DIAGNOSIS][ERROR] {vehicle_id}: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_diagnosis()
