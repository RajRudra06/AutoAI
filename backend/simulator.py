import time
import random
import requests

URL = "http://127.0.0.1:8000/telematics/data"
vehicle_ids = ["V001", "V002", "V003"]

def send_data():
    while True:
        data = {
            "vehicle_id": random.choice(vehicle_ids),
            "engine_temp": random.randint(70, 130),
            "battery_health": random.randint(20, 100),
            "fuel_level": random.randint(5, 60),
            "tyre_pressure": random.randint(20, 40),
            "odometer": random.randint(10000, 90000),
        }
        res = requests.post(URL, json=data)
        print("Sent:", data)
        time.sleep(4)

if __name__ == "__main__":
    send_data()
