# import time
# import requests
# from datetime import datetime, timezone
# import os
# from dotenv import load_dotenv

# from crewai import Agent, Task, Crew
# from agents.utils.agent_api_client import get, post

# # ─────────────────────────────────────────────
# # ENV SETUP
# # ─────────────────────────────────────────────
# load_dotenv()

# BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

# GET_VEHICLES_STATE_URL = f"{BASE_API_URL}/api/vehicles/state"
# GET_VEHICLE_PREDICTION = f"{BASE_API_URL}/api/predictions"
# GET_VEHICLE_SCHEDULE = f"{BASE_API_URL}/api/schedule"
# ENGAGEMENT_LOG_URL = f"{BASE_API_URL}/api/engagement/log"
# UPDATE_VEHICLE_STATE = f"{BASE_API_URL}/api/vehicle_state/update"

# POLL_INTERVAL = 15

# # ─────────────────────────────────────────────
# # CREW AI AGENT
# # ─────────────────────────────────────────────
# engagement_llm_agent = Agent(
#     role="Customer Engagement Specialist",
#     goal=(
#         "Explain vehicle issues clearly, reassure the customer, "
#         "and guide them toward service completion."
#     ),
#     backstory=(
#         "You are an automotive service advisor AI. "
#         "You receive technical diagnoses and must translate them "
#         "into calm, actionable customer communication."
#     ),
#     verbose=True
# )

# def build_engagement_task(vehicle_id, prediction, booking):
#     description = f"""
#     Vehicle ID: {vehicle_id}

#     Diagnosis Summary:
#     {prediction}

#     Booking Details:
#     {booking}

#     Task:
#     - Write a short, clear message to the customer.
#     - Explain the issue severity without panic.
#     - Mention the scheduled service.
#     - Ask for confirmation or approval if needed.
#     """

#     return Task(
#         description=description,
#         expected_output="A customer-facing message explaining the issue and next steps.",
#         agent=engagement_llm_agent
#     )

# def run_crewai_engagement(vehicle_id, prediction, booking):
#     task = build_engagement_task(vehicle_id, prediction, booking)

#     crew = Crew(
#         agents=[engagement_llm_agent],
#         tasks=[task],
#         verbose=True
#     )

#     return crew.kickoff()

# # ─────────────────────────────────────────────
# # MAIN LOOP
# # ─────────────────────────────────────────────
# def run_engagement_agent():
#     print("[ENGAGEMENT] Agent started.")

#     while True:
#         resp = get(GET_VEHICLES_STATE_URL)
#         vehicles = resp.json().get("vehicles", [])

#         for v in vehicles:
#             vehicle_id = v["vehicle_id"]
#             flags = v["workflow_state"]["flags"]
#             current_stage = v["workflow_state"].get("current_stage")

#             # ✅ one-time execution guard
#             if current_stage == "ENGAGEMENT_COMPLETE":
#                 continue

#             if not flags.get("engagement_required"):
#                 continue

#             # 1️⃣ Fetch prediction
#             pred = get(
#                 f"{GET_VEHICLE_PREDICTION}/{vehicle_id}"
#             ).json().get("data")

#             # 2️⃣ Fetch booking
#             booking = get(
#                 f"{GET_VEHICLE_SCHEDULE}/{vehicle_id}"
#             ).json().get("data")

#             if not pred or not booking:
#                 continue

#             # 3️⃣ ONE LLM ATTEMPT ONLY
#             try:
#                 message = run_crewai_engagement(vehicle_id, pred, booking)
#                 message_text = str(message)
#             except Exception as e:
#                 print(f"[ENGAGEMENT] LLM failed for {vehicle_id}: {e}")
#                 message_text = (
#                     f"Your vehicle {vehicle_id} has a detected issue. "
#                     f"A service is scheduled on {booking['slot']} at {booking['center_id']}."
#                 )

#             # 4️⃣ Log engagement (always)
#             post(
#                 ENGAGEMENT_LOG_URL,
#                 json={
#                     "vehicle_id": vehicle_id,
#                     "message": message_text,
#                     "created_at": datetime.now(timezone.utc).isoformat()
#                 }
#             )

#             # 5️⃣ Advance workflow (always)
#             requests.post(
#                 UPDATE_VEHICLE_STATE,
#                 json={
#                     "vehicle_id": vehicle_id,
#                     "workflow_state": {
#                         "current_stage": "ENGAGEMENT_COMPLETE",
#                         "flags": {
#                             "engagement_required": False
#                         }
#                     }
#                 }
#             )

#             print(f"[ENGAGEMENT] Completed for {vehicle_id}")

#         time.sleep(POLL_INTERVAL)

# # ─────────────────────────────────────────────
# if __name__ == "__main__":
#     run_engagement_agent()

import time
import requests
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

from crewai import Agent, Task, Crew
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

POLL_INTERVAL = 15

# ─────────────────────────────────────────────
# CREW AI AGENT (KEPT)
# ─────────────────────────────────────────────
# engagement_llm_agent = Agent(
#     role="Customer Engagement Specialist",
#     goal=(
#         "Explain vehicle issues clearly, reassure the customer, "
#         "and guide them toward service completion."
#     ),
#     backstory=(
#         "You are an automotive service advisor AI. "
#         "You receive technical diagnoses and must translate them "
#         "into calm, actionable customer communication."
#     ),
#     verbose=True
# )

def build_engagement_task(vehicle_id, prediction, booking):
    description = f"""
    Vehicle ID: {vehicle_id}

    Diagnosis Summary:
    {prediction}

    Booking Details:
    {booking}

    Task:
    - Write a short, clear message to the customer.
    - Explain the issue severity without panic.
    - Mention the scheduled service.
    - Ask for confirmation or approval if needed.
    """

    return Task(
        description=description,
        expected_output="A customer-facing message explaining the issue and next steps.",
        agent=engagement_llm_agent
    )

def run_crewai_engagement(vehicle_id, prediction, booking):
    task = build_engagement_task(vehicle_id, prediction, booking)

    crew = Crew(
        agents=[engagement_llm_agent],
        tasks=[task],
        verbose=True
    )

    return crew.kickoff()

# ─────────────────────────────────────────────
# MOCK LLM (LLM-LIKE + PRINTING)
# ─────────────────────────────────────────────
def mock_llm_engagement_response(vehicle_id, prediction, booking):
    risk_level = prediction.get("risk_level", "MODERATE")
    slot = booking.get("slot")
    center = booking.get("center_id")

    if risk_level == "HIGH":
        severity_line = (
            "Our diagnostics have identified a condition that may affect your "
            "vehicle’s performance if not addressed promptly."
        )
    else:
        severity_line = (
            "Our routine diagnostics have identified a condition that requires attention."
        )

    message = (
        f"Dear Customer,\n\n"
        f"{severity_line}\n\n"
        f"A service appointment has been scheduled for your vehicle (ID: {vehicle_id}) "
        f"on {slot} at our authorized service center ({center}).\n\n"
        f"Our service team will perform a detailed inspection and take the necessary "
        f"corrective actions to ensure continued safety and reliability.\n\n"
        f"If the scheduled time works for you, no further action is required. "
        f"If you prefer a different time, please contact us to reschedule.\n\n"
        f"Best regards,\n"
        f"Customer Support Team"
    )

    # 🔹 CrewAI-style console output
    print("\n" + "═" * 90)
    print("🤖 Agent: Customer Engagement Specialist")
    print(f"📋 Vehicle ID: {vehicle_id}")
    print(f"⚠️  Risk Level: {risk_level}")
    print("🧠 Generating customer message...\n")
    print(message)
    print("═" * 90 + "\n")

    return {
        "content": message,
        "model": "mock-llm-v1",
        "confidence": "high"
    }

# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
def run_engagement_agent():
    print("[ENGAGEMENT] Agent started.\n")

    while True:
        resp = get(GET_VEHICLES_STATE_URL)
        vehicles = resp.json().get("vehicles", [])

        for v in vehicles:
            vehicle_id = v["vehicle_id"]
            flags = v["workflow_state"]["flags"]
            current_stage = v["workflow_state"].get("current_stage")

            if current_stage == "ENGAGEMENT_COMPLETE":
                continue

            if not flags.get("engagement_required"):
                continue

            pred = get(
                f"{GET_VEHICLE_PREDICTION}/{vehicle_id}"
            ).json().get("data")

            booking = get(
                f"{GET_VEHICLE_SCHEDULE}/{vehicle_id}"
            ).json().get("data")

            if not pred or not booking:
                continue

            # ✅ MOCK LLM (prints like real LLM)
            mock_response = mock_llm_engagement_response(
                vehicle_id, pred, booking
            )
            message_text = mock_response["content"]

            post(
                ENGAGEMENT_LOG_URL,
                json={
                    "vehicle_id": vehicle_id,
                    "message": message_text,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            )

            post(
                UPDATE_VEHICLE_STATE,
                json={
                    "vehicle_id": vehicle_id,
                    "workflow_state": {
                        "current_stage": "ENGAGEMENT_COMPLETE",
                        "flags": {
                            "engagement_required": False
                        }
                    }
                }
            )

            print(f"[ENGAGEMENT] Completed for {vehicle_id}\n")

        time.sleep(POLL_INTERVAL)

# ─────────────────────────────────────────────
if __name__ == "__main__":
    run_engagement_agent()
