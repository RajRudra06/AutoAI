import time
import requests
from datetime import datetime, timezone

from crewai import Agent, Task, Crew

API_BASE = "http://127.0.0.1:8000"
HEADERS = {"Authorization": "Bearer AGENT_TOKEN_ENGAGEMENT"}
POLL_INTERVAL = 15

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
    verbose=True
)

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
        expected_output=(
            "A customer-facing message explaining the issue and next steps."
        ),
        agent=engagement_llm_agent
    )


def run_crewai_engagement(vehicle_id, prediction, booking):
    task = build_engagement_task(vehicle_id, prediction, booking)

    crew = Crew(
        agents=[engagement_llm_agent],
        tasks=[task],
        verbose=True
    )

    result = crew.kickoff()
    return result


def run_engagement_agent():
    print("[ENGAGEMENT] Agent started.")

    while True:
        # 1️⃣ Fetch vehicles
        resp = requests.get(f"{API_BASE}/vehicle_state/list", headers=HEADERS)
        vehicles = resp.json()["vehicles"]

        for v in vehicles:
            vehicle_id = v["vehicle_id"]
            flags = v["workflow_state"]["flags"]

            if not flags.get("engagement_required"):
                continue

            # 2️⃣ Fetch prediction
            pred = requests.get(
                f"{API_BASE}/predictions/{vehicle_id}",
                headers=HEADERS
            ).json()["data"]

            # 3️⃣ Fetch booking
            booking = requests.get(
                f"{API_BASE}/schedule/{vehicle_id}",
                headers=HEADERS
            ).json()["data"]

            # ✅ Improvement 1: guard against missing data
            if not pred or not booking:
                continue

            # 4️⃣ Run CrewAI
            message = run_crewai_engagement(vehicle_id, pred, booking)

            # ✅ Improvement 2: safe conversion of CrewAI output
            message_text = str(message)

            # 5️⃣ Log engagement
            requests.post(
                f"{API_BASE}/engagement/log",
                json={
                    "vehicle_id": vehicle_id,
                    "message": message_text,
                    "created_at": datetime.now(timezone.utc).isoformat()
                },
                headers=HEADERS
            )

            # 6️⃣ Advance workflow
            requests.post(
                f"{API_BASE}/vehicle_state/update",
                json={
                    "vehicle_id": vehicle_id,
                    "workflow_state": {
                        "current_stage": "ENGAGEMENT_COMPLETE",
                        "flags": {
                            "engagement_required": False
                        }
                    }
                },
                headers=HEADERS
            )

            print(f"[ENGAGEMENT] Completed for {vehicle_id}")

        time.sleep(POLL_INTERVAL)
