# agents/collector_agent.py

import time
import pandas as pd
import requests

from backend.raw_data_generator import RawDataGenerator, VEHICLE_IDS
from helpers.logic.generate_feature_simulator import extract_features_from_vehicle

READINGS_PER_VEHICLE = 120
SLEEP_SECONDS = 10
MOCK_API_URL = "http://127.0.0.1:8000/telematics/data"


def to_json_safe(obj):
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if hasattr(obj, "item"):  # numpy scalar → python scalar
        return obj.item()
    return obj


class CollectorAgent:
    def __init__(self):
        self.generator = RawDataGenerator()

    def run(self):
        print("[COLLECTOR] Agent started")

        while True:
            print("\n🚀 Generating telemetry window...")

            windows = self.generator.generate_window(
                n_readings=READINGS_PER_VEHICLE
            )

            for vid, rows in windows.items():
                df = pd.DataFrame(rows)
                features = extract_features_from_vehicle(df)

                payload = {
                    "vehicle_id": vid,
                    "timestamp": df.iloc[-1]["timestamp"].isoformat(),
                    "features": to_json_safe(features)  # 🔴 critical line
                }

                try:
                    requests.post(MOCK_API_URL, json=payload, timeout=2)
                    print(f"✅ Sent 43-feature summary for {vid}")
                except Exception as e:
                    print(f"❌ Failed for {vid}: {e}")

            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    CollectorAgent().run()
