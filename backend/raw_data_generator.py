# simulator/raw_data_generator.py

import random
from datetime import datetime, timedelta

VEHICLE_IDS = ["V001", "V002", "V003", "V004", "V005"]
FAILING_VEHICLES = {"V004"}


class RawDataGenerator:
    def __init__(self):
        self.state = {}
        for vid in VEHICLE_IDS:
            self.state[vid] = {
                "vehicle_id": vid,
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

    def evolve(self, v, failing=False):
        v["engine_temp_c"] += random.uniform(0.1, 0.3 if failing else 0.15)
        v["oil_pressure_psi"] -= random.uniform(0.05, 0.15 if failing else 0.08)
        v["brake_pad_mm"] -= random.uniform(0.01, 0.04 if failing else 0.02)
        v["battery_voltage_v"] -= random.uniform(0.001, 0.01)
        v["vibration_level"] += random.uniform(0.01, 0.05 if failing else 0.02)
        v["transmission_temp_c"] += random.uniform(0.1, 0.3)
        v["coolant_temp_c"] += random.uniform(0.05, 0.2)
        v["engine_rpm"] += random.randint(-100, 200)
        v["daily_miles"] = random.randint(40, 90)
        v["harsh_braking_events"] += random.randint(0, 1)
        v["harsh_acceleration_events"] += random.randint(0, 2)
        v["cold_starts"] = random.randint(0, 1)
        v["fuel_consumption_l_per_100km"] += random.uniform(-0.2, 0.3)
        v["miles_since_last_service"] += random.randint(5, 30)
        v["timestamp"] += timedelta(minutes=30)
        return v

    def generate_window(self, n_readings=120):
        """
        Generates N raw readings per vehicle.
        Returns dict: {vehicle_id: [rows]}
        """
        output = {}

        for vid, v in self.state.items():
            failing = vid in FAILING_VEHICLES
            history = []

            for _ in range(n_readings):
                self.state[vid] = self.evolve(v, failing)
                history.append(self.state[vid].copy())

            output[vid] = history

        return output
