import time
import joblib
import numpy as np
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

from backend.db.connection import db
from helpers.logic.get_feature_name import get_feature_names
from helpers.logic.risk_scoring import transform_scores_to_risk
from agents.utils.agent_api_client import post, get

load_dotenv()

POLL_INTERVAL = 10  # seconds

MODEL_PATH = "diag_agent_model/iForest/models/isolation_forest_v1.pkl"
MODEL_VERSION = "isolation_forest_v1"
FEATURE_VERSION = "v1"
WINDOW_SIZE = 120

BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
GET_DIAGNOSIS_JOBS_API_URL = f"{BASE_API_URL}/api/diagnosis/jobs"
START_JOB_URL = f"{BASE_API_URL}/api/diagnosis/start"
COMPLETE_JOB_URL = f"{BASE_API_URL}/api/diagnosis/complete"
SKIP_JOB_URL = f"{BASE_API_URL}/api/diagnosis/skip"
FAIL_JOB_URL = f"{BASE_API_URL}/api/diagnosis/fail"
GET_VEHICLE_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"


print("[DIAGNOSIS] Loading ML model...")
model = joblib.load(MODEL_PATH)
FEATURE_ORDER = get_feature_names()
print("[DIAGNOSIS] Model loaded.")


def run_diagnosis():
    print("[DIAGNOSIS] Agent started. Waiting for jobs...")

    while True:

        resp = get(GET_DIAGNOSIS_JOBS_API_URL)
        jobs = resp.json().get("jobs", [])

        for job in jobs:
            job_id = job["_id"]
            vehicle_id = job["vehicle_id"]
            features_dict = job["features_snapshot"]
            unresolved_issues = job.get("trigger_reasons", [])

            # ================================
            # 🚫 LIFECYCLE GATE (NEW)
            # ================================
            vehicle_resp = get(
                f"{GET_VEHICLE_STATE_URL}/{vehicle_id}"
            )

            if vehicle_resp.status_code == 200:
                state = vehicle_resp.json()
                stage = state.get("workflow_state", {}).get("current_stage")
                high_risk = state.get("risk_state", {}).get("high_risk_active", False)

                if stage in {"DIAGNOSIS_COMPLETE", "SCHEDULING", "IN_SERVICE"} or high_risk:
                    post(
                        SKIP_JOB_URL,
                        json={
                            "job_id": job_id,
                            "reason": "Lifecycle gate active"
                        }
                    )
                    continue

            # Mark job in progress
            try:
                post(START_JOB_URL, json={"job_id": job_id})
            except Exception:
                continue  # someone else took it

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

                payload = {
                    "job_id": job_id,
                    "vehicle_id": vehicle_id,
                    "anomaly_score": anomaly_score,
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "features_snapshot": features_dict,
                    "unresolved_issues": unresolved_issues,
                    "feature_version": FEATURE_VERSION,
                    "window_size": WINDOW_SIZE,
                    "model_version": MODEL_VERSION
                }

                post(COMPLETE_JOB_URL, json=payload)

                print(
                    f"[DIAGNOSIS][DONE] {vehicle_id} | "
                    f"risk={risk_level} | score={risk_score:.3f}"
                )

            except Exception as e:
                post(
                    FAIL_JOB_URL,
                    json={
                        "job_id": job_id,
                        "error": str(e)
                    }
                )
                print(f"[DIAGNOSIS][ERROR] {vehicle_id}: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_diagnosis()