import random
import time
from datetime import datetime, timedelta
import requests
import pandas as pd

from helpers.logic.generate_feature_simulator import extract_features_from_vehicle

URL = "http://127.0.0.1:8000/telematics/data"

VEHICLE_IDS = ["V001", "V002", "V003", "V004", "V005"]
READINGS_PER_VEHICLE = 120
READINGS_PER_LOOP = 20
LOOPS = READINGS_PER_VEHICLE // READINGS_PER_LOOP
SLEEP_SECONDS = 10

# Vehicles that degrade faster (for realism)
FAILING_VEHICLES = {"V004"}

vehicle_state = {}

for vid in VEHICLE_IDS:
    vehicle_state[vid] = {
        "engine_temp_c": random.uniform(85, 95),
        "oil_pressure_psi": random.uniform(35, 45),
        "brake_pad_mm": random.uniform(7, 10),
        "battery_voltage_v": random.uniform(12.3, 12.7),
        "vibration_level": random.uniform(0.1, 0.3),
        "transmission_temp_c": random.uniform(70, 85),
        "coolant_temp_c": random.uniform(75, 85),

        "tire_pressure_fl": random.uniform(30, 34),
        "tire_pressure_fr": random.uniform(30, 34),
        "tire_pressure_rl": random.uniform(30, 34),
        "tire_pressure_rr": random.uniform(30, 34),

        "engine_rpm": random.randint(1500, 2500),
        "daily_miles": random.randint(40, 80),
        "harsh_braking_events": 0,
        "harsh_acceleration_events": 0,
        "cold_starts": 0,
        "fuel_consumption_l_per_100km": random.uniform(7, 11),
        "miles_since_last_service": random.randint(2000, 6000),

        "timestamp": datetime.utcnow(),
    }


def evolve(state: dict, failing: bool) -> dict:
    state["engine_temp_c"] += random.uniform(0.1, 0.3 if failing else 0.15)
    state["oil_pressure_psi"] -= random.uniform(0.05, 0.15 if failing else 0.08)
    state["brake_pad_mm"] -= random.uniform(0.01, 0.04 if failing else 0.02)
    state["battery_voltage_v"] -= random.uniform(0.001, 0.01)
    state["vibration_level"] += random.uniform(0.01, 0.05 if failing else 0.02)

    state["transmission_temp_c"] += random.uniform(0.1, 0.3)
    state["coolant_temp_c"] += random.uniform(0.05, 0.2)
    state["engine_rpm"] += random.randint(-100, 200)

    state["daily_miles"] = random.randint(40, 90)
    state["harsh_braking_events"] += random.randint(0, 1)
    state["harsh_acceleration_events"] += random.randint(0, 2)
    state["cold_starts"] = random.randint(0, 1)
    state["fuel_consumption_l_per_100km"] += random.uniform(-0.2, 0.3)

    state["miles_since_last_service"] += random.randint(5, 30)
    state["timestamp"] += timedelta(minutes=30)

    return state

def to_json_safe(d: dict) -> dict:
    """Convert numpy types to native Python types for JSON serialization."""
    safe = {}
    for k, v in d.items():
        if hasattr(v, "item"):   # numpy scalar
            safe[k] = v.item()
        else:
            safe[k] = v
    return safe

def run_simulator():
    print("[SIMULATOR] Started.")

    while True:
        print("\n🚀 Generating telemetry window...")

        for vid in VEHICLE_IDS:
            history = []
            state = vehicle_state[vid]
            failing = vid in FAILING_VEHICLES

            for _ in range(LOOPS):
                for _ in range(READINGS_PER_LOOP):
                    state = evolve(state, failing)
                    history.append(state.copy())

            df = pd.DataFrame(history)

            # --- Feature extraction (core step)
            raw_features = extract_features_from_vehicle(df)
            features = to_json_safe(raw_features)

            payload = {
                "vehicle_id": vid,
                "timestamp": df.iloc[-1]["timestamp"].isoformat(),
                "features": features,
            }

            try:
                requests.post(URL, json=payload, timeout=2)
                print(f"✅ Sent 43-feature summary for {vid}")
            except Exception as e:
                print(f"❌ Failed for {vid}: {e}")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    run_simulator()
