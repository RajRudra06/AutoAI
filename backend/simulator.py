import time
import random
import requests

URL = "http://127.0.0.1:8000/telematics/data"

vehicle_ids = ["V001", "V002", "V003", "V004", "V005"]

def send_data():
    while True:
        data = {
            "vehicle_id": random.choice(vehicle_ids),

            # Engine & powertrain
            "engine_temp": random.randint(70, 135),        # °C
            "rpm": random.randint(800, 4500),
            "vibration": round(random.uniform(0.05, 0.6), 2),

            # Electrical
            "battery_health": random.randint(20, 100),     # %

            # Fluids
            "fuel_level": random.randint(0, 60),           # %
            "oil_health": random.randint(40, 100),         # %

            # Tyres & brakes
            "tyre_pressure": random.randint(18, 40),       # PSI
            "brake_wear": round(random.uniform(0.1, 0.95), 2),

            # Usage
            "odometer": random.randint(10_000, 120_000)
        }

        try:
            res = requests.post(URL, json=data)
            print("Sent:", data, "| Status:", res.status_code)
        except Exception as e:
            print("Error:", e)

        time.sleep(15)

if __name__ == "__main__":
    send_data()
