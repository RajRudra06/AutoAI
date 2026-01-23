# enagagement_agent

import time
import requests
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

from helpers.logic.email_service import send_email

from crewai import Agent, Task, Crew
from crewai.llm import LLM

from agents.utils.agent_api_client import get, post

# ─────────────────────────────────────────────
# ENV SETUP
# ─────────────────────────────────────────────
load_dotenv()

BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

GET_VEHICLES_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"
GET_VEHICLE_PREDICTION = f"{BASE_API_URL}/api/predictions"
GET_VEHICLE_SCHEDULE = f"{BASE_API_URL}/api/schedule"
ENGAGEMENT_LOG_URL = f"{BASE_API_URL}/api/engagement/log"
UPDATE_VEHICLE_STATE = f"{BASE_API_URL}/api/vehicles/update"

POLL_INTERVAL = 3

SEVEN_DAY_RULES = {
    # Engine temperature
    "engine_temp_mean_7d": {
        "threshold": 105,
        "unit": "°C",
        "category": "engine_temperature"
    },
    "engine_temp_max_7d": {
        "threshold": 110,
        "unit": "°C",
        "category": "engine_temperature"
    },
    "engine_temp_std_7d": {
        "threshold": 2.0,
        "unit": "°C",
        "category": "engine_temperature_stability"
    },

    # Oil pressure
    "oil_pressure_mean_7d": {
        "threshold": 30,
        "unit": "psi",
        "category": "oil_pressure"
    },
    "oil_pressure_min_7d": {
        "threshold": 28,
        "unit": "psi",
        "category": "oil_pressure"
    },
    "oil_pressure_std_7d": {
        "threshold": 1.0,
        "unit": "psi",
        "category": "oil_pressure_stability"
    },

    # Battery
    "battery_voltage_mean_7d": {
        "threshold": 12.0,
        "unit": "V",
        "category": "battery_health"
    },
    "battery_voltage_min_7d": {
        "threshold": 11.8,
        "unit": "V",
        "category": "battery_health"
    },

    # Coolant
    "coolant_temp_mean_7d": {
        "threshold": 95,
        "unit": "°C",
        "category": "coolant_temperature"
    },
    "coolant_temp_max_7d": {
        "threshold": 100,
        "unit": "°C",
        "category": "coolant_temperature"
    },

    # Vibration
    "vibration_mean_7d": {
        "threshold": 2.0,
        "unit": "g",
        "category": "vibration"
    },
    "vibration_max_7d": {
        "threshold": 2.5,
        "unit": "g",
        "category": "vibration"
    },

    # Transmission
    "transmission_temp_mean_7d": {
        "threshold": 100,
        "unit": "°C",
        "category": "transmission_temperature"
    },
    "transmission_temp_max_7d": {
        "threshold": 105,
        "unit": "°C",
        "category": "transmission_temperature"
    }
}

# ─────────────────────────────────────────────
# CREW AI AGENT (KEPT)
# ─────────────────────────────────────────────
groq_llm = LLM(
    model="groq/llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)

engagement_llm_agent = Agent(
    role="Customer Engagement Specialist",
    goal=(
        "Explain vehicle issues clearly, reassure the customer, "
        "and guide them toward service completion."
    ),
    backstory=(
        "You are an automotive service advisor AI. "
        "You receive technical diagnoses and must translate them "
        "into calm, actionable customer communication."
    ),
    llm=groq_llm,
    verbose=True
)

def build_engagement_task(vehicle_id, issue, booking):
    description = f"""
    Vehicle ID: {vehicle_id}

    Diagnosis Summary:
    {issue}

    Booking Details:
    {booking}

    Task:
    - Write a short 20 words clear message to the customer.
    - Explain the issue severity without panic.
    - All the top issues are mentioned in the diagnosis summary dictornary with thier severity and their thresholds.
    - Mention the scheduled service.
    - Just have the message as your reply, do not put it into "" or have more sentence after the message.
    - Ask for confirmation or approval if needed.
    """

    return Task(
        description=description,
        expected_output="A customer-facing message explaining the issue and next steps.",
        agent=engagement_llm_agent
    )

def run_crewai_engagement(vehicle_id, issue, booking):
    task = build_engagement_task(vehicle_id, issue, booking)

    crew = Crew(
        agents=[engagement_llm_agent],
        tasks=[task],
        verbose=True
    )

    return crew.kickoff()

def compute_severity(value, threshold):
    return abs(value - threshold) / threshold

def extract_7d_top_issues(vehicle_id, features_snapshot):
    issues = []

    for feature, rule in SEVEN_DAY_RULES.items():
        if feature not in features_snapshot:
            continue

        value = features_snapshot[feature]
        threshold = rule["threshold"]

        severity = compute_severity(value, threshold)

        issues.append({
            "feature": feature,
            "category": rule["category"],
            "value": round(value, 3),
            "threshold": threshold,
            "unit": rule["unit"],
            "severity": round(severity, 4)
        })

    issues.sort(key=lambda x: x["severity"], reverse=True)

    top_issues = issues[:6]


    return {
        "vehicle_id": vehicle_id,
        "issues": top_issues
    }


def mock_llm_engagement_response(vehicle_id, prediction, booking):
    risk_level = prediction.get("risk_level", "MODERATE")
    issues = prediction.get("issues", [])
    slot = booking.get("slot")
    center = booking.get("center_id")

    # Severity framing
    if risk_level == "HIGH":
        opening = (
            "This is an important update regarding your vehicle. "
            "Our diagnostics indicate a condition that may impact safety or performance."
        )
        urgency = "We recommend addressing this at the earliest opportunity."
    else:
        opening = (
            "This is a routine service update regarding your vehicle."
        )
        urgency = "While not urgent, timely service is recommended."

    # Issue summary
    if issues:
        issue_lines = ", ".join(
            f"{i['component']} ({i['issue']})" for i in issues
        )
        issue_text = f"Our system detected concerns related to: {issue_lines}."
    else:
        issue_text = "Our system detected a general maintenance requirement."

    message = (
        f"{opening}\n\n"
        f"{issue_text}\n"
        f"{urgency}\n\n"
        f"A service appointment has been scheduled for your vehicle (ID {vehicle_id}) "
        f"on {slot} at our authorized service center {center}.\n\n"
        f"If this time works for you, no action is needed. "
        f"If you wish to reschedule, please contact our support team.\n\n"
        f"Thank you for choosing us. We’re committed to keeping your vehicle safe and reliable."
    )

    # Console trace (LLM-like)
    print("\n" + "═" * 90)
    print("🤖 Agent: Customer Engagement Specialist (MOCK LLM)")
    print(f"📋 Vehicle ID: {vehicle_id}")
    print(f"⚠️  Risk Level: {risk_level}")
    print("🧠 Generating customer message...\n")
    print(message)
    print("═" * 90 + "\n")

    return {
        "content": message,
        "risk_level": risk_level,
        "tone": "reassuring" if risk_level != "HIGH" else "urgent",
        "model": "mock-llm-v2",
        "confidence": 0.95
    }


def run_engagement_agent():
    print("[ENGAGEMENT] Agent started.")
    print(f"[ENGAGEMENT] Polling every {POLL_INTERVAL}s")
    print(f"[ENGAGEMENT] Backend URL: {BASE_API_URL}\n")

    while True:
        print("[ENGAGEMENT] Fetching vehicle states...")
        resp = get(GET_VEHICLES_STATE_URL)

        if resp.status_code != 200:
            print(f"[ERROR] Failed to fetch vehicles state: {resp.status_code}")
            time.sleep(POLL_INTERVAL)
            continue

        vehicles = resp.json().get("vehicles", [])
        print(f"[ENGAGEMENT] Vehicles received: {len(vehicles)}")

        for v in vehicles:
            vehicle_id = v["vehicle_id"]
            flags = v["workflow_state"]["flags"]
            current_stage = v["workflow_state"].get("current_stage")
            risk_state = v["risk_state"]

            print(f"\n[VEHICLE] Processing {vehicle_id}")
            print(f"  ├─ Current stage: {current_stage}")
            print(f"  ├─ Flags: {flags}")
            print(f"  └─ Risk state: {risk_state}")

            if current_stage == "ENGAGEMENT_COMPLETE":
                print("  ⏭ Skipping: engagement already completed")
                continue

            if not flags.get("engagement_required"):
                print("  ⏭ Skipping: engagement not required")
                continue

            print("  ▶ Fetching prediction...")
            pred_resp = get(f"{GET_VEHICLE_PREDICTION}/{vehicle_id}")
            pred = pred_resp.json().get("data") if pred_resp.status_code == 200 else None

            issues=extract_7d_top_issues(vehicle_id=vehicle_id,features_snapshot=pred["features_snapshot"])

            if not pred:
                print("  ❌ Prediction missing, skipping vehicle")
                continue

            print("  ✔ Prediction received")

            print("  ▶ Fetching booking...")
            booking_resp = get(f"{GET_VEHICLE_SCHEDULE}/{vehicle_id}")
            booking = booking_resp.json().get("data") if booking_resp.status_code == 200 else None

            if not booking:
                print("  ❌ Booking missing or expired, skipping vehicle")
                continue

            print("  ✔ Booking received")

            print("  ▶ Generating engagement message...")
            try:

                crew_output = run_crewai_engagement(vehicle_id, issues, booking)
                message_text = str(crew_output)
            except Exception as e:
                print(f"❌ Engagement failed for {vehicle_id}: {e}")
                continue

            print("  ✔ Message generated")

            print("  ▶ Sending email...")
            try:
                send_email(
                    to_email="customer@example.com",
                    subject="Important Update About Your Vehicle",
                    body=message_text
                )
                print("  ✔ Email sent")
            except Exception as e:
                print(f"  ❌ Email failed: {e}")
                continue

            print("  ▶ Logging engagement...")
            post(
                ENGAGEMENT_LOG_URL,
                json={
                    "vehicle_id": vehicle_id,
                    "message": message_text,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            )
            print("  ✔ Engagement logged")

            print("  ▶ Updating vehicle workflow state...")
            post(
                UPDATE_VEHICLE_STATE,
                json={
                    "vehicle_id": vehicle_id,
                    "workflow_state": {
                        "current_stage": "ENGAGEMENT_COMPLETE",
                        "flags": {
                            "engagement_required": False
                        }
                    },
                    "risk_state": risk_state
                }
            )

            print(f"[ENGAGEMENT] ✅ Completed for {vehicle_id}")
            time.sleep(3)

        print(f"\n[ENGAGEMENT] Sleeping for {POLL_INTERVAL}s...\n")
        time.sleep(POLL_INTERVAL)


# ─────────────────────────────────────────────
if __name__ == "__main__":
    run_engagement_agent()
