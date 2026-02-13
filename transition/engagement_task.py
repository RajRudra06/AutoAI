import time
import requests
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

from helpers.logic.email_service import send_email

# CrewAI imports - ensure these are available in the Celery worker environment
from crewai import Agent, Task, Crew
from crewai.llm import LLM # Assuming LLM is from crewai.llm directly

from agents.utils.agent_api_client import get, post
from worker_tasks.celery_config import app # Assuming 'app' is the Celery app instance

load_dotenv()

# --- Global Constants and Configurations (Moved from original agent) ---
BASE_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

# API Endpoints
GET_VEHICLE_PREDICTION = f"{BASE_API_URL}/api/predictions"
GET_VEHICLE_SCHEDULE = f"{BASE_API_URL}/api/schedule"
ENGAGEMENT_LOG_URL = f"{BASE_API_URL}/api/engagement/log"
UPDATE_VEHICLE_STATE = f"{BASE_API_URL}/api/vehicles/update"

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

# CREW AI AGENT (KEPT) - Initialized globally so it's loaded once per worker process
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
    verbose=False
)

def build_engagement_task_celery(vehicle_id, issue, booking):
    description = f"""
    Vehicle ID: {vehicle_id}

    Diagnosis Summary:
    {issue}

    Booking Details:
    {booking}

    Task:
    - Output ONLY the final customer message.
    - Do NOT include Thought, Reasoning, Analysis, or explanations.
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

def run_crewai_engagement_celery(vehicle_id, issue, booking):
    task = build_engagement_task_celery(vehicle_id, issue, booking)

    crew = Crew(
        agents=[engagement_llm_agent],
        tasks=[task],
        verbose=True
    )

    return crew.kickoff()

def compute_severity_celery(value, threshold):
    return abs(value - threshold) / threshold

def extract_7d_top_issues_celery(vehicle_id, features_snapshot):
    issues = []

    for feature, rule in SEVEN_DAY_RULES.items():
        if feature not in features_snapshot:
            continue

        value = features_snapshot[feature]
        threshold = rule["threshold"]

        severity = compute_severity_celery(value, threshold)

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


def mock_llm_engagement_response_celery(vehicle_id, prediction, booking):
    # --- Normalize inputs ---
    risk_level = prediction.get("risk_level", "MODERATE")
    issues = prediction.get("issues", [])

    slot = booking.get("slot")
    if not slot or slot == '{"data":false}':
        slot = "the scheduled service slot"

    center = booking.get("center_id", "our authorized service center")

    # --- Severity framing ---
    if risk_level == "HIGH":
        opening = "This is an important update regarding your vehicle."
        urgency = "We recommend addressing this soon to avoid potential issues."
        tone = "urgent"
    elif risk_level == "LOW":
        opening = "This is a routine update regarding your vehicle."
        urgency = "No immediate action is required."
        tone = "reassuring"
    else:
        opening = "This is a service update regarding your vehicle."
        urgency = "Timely service is recommended."
        tone = "reassuring"

    # --- Issue summarization (generic) ---
    if issues:
        summarized = []
        for i in issues[:3]:
            category = i.get("category", "system")
            value = i.get("value")
            threshold = i.get("threshold")
            unit = i.get("unit", "")

            if value is not None and threshold is not None:
                summarized.append(f"{category} near threshold ({value}{unit})")
            else:
                summarized.append(category)

        issue_text = (
            "Our diagnostics identified the following indicators: "
            + ", ".join(summarized) + "."
        )
    else:
        issue_text = "Our diagnostics identified routine maintenance indicators."

    # --- Final message ---
    message = (
        f"{opening} "
        f"{issue_text} "
        f"{urgency} "
        f"A service appointment is scheduled for vehicle {vehicle_id} "
        f"at {center}. "
        f"Please confirm or request rescheduling if needed."
    )

    # --- Console trace ---
    print("" + "═" * 90)
    print("🤖 Agent: Customer Engagement Specialist (MOCK LLM)")
    print(f"📋 Vehicle ID: {vehicle_id}")
    print(f"⚠️  Risk Level: {risk_level}")
    print("🧠 Generating customer message...")
    print(message)
    print("═" * 90 + "")

    return {
        "content": message,
        "risk_level": risk_level,
        "tone": tone,
        "model": "mock-llm-v3-generic",
        "confidence": 0.97
    }


@app.task(
    bind=True,
    name='tasks.execute_engagement.execute_engagement_job', # New task name
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def execute_engagement_job(self, vehicle_id: str, base_api_url: str, risk_state: dict):
    my_task_id = self.request.id
    print(f"[ENGAGEMENT TASK] Starting execution for vehicle {vehicle_id}, task_id={my_task_id}")

    # Pre-execution verification step
    print(f"Task {my_task_id}: Verifying state for vehicle {vehicle_id} before execution.")
    try:
        vehicle_state_resp = get(f"{base_api_url}/api/vehicles/state/{vehicle_id}")
        vehicle_state_resp.raise_for_status()
        current_vehicle_data = vehicle_state_resp.json()
    except Exception as e:
        print(f"Task {my_task_id}: ABORTING. Could not fetch state for vehicle {vehicle_id}. Error: {e}")
        # Need a way to mark engagement job as failed if verification fails
        return # Abort if we can't verify the state

    pipeline_data = current_vehicle_data.get("pipeline_associated", {})

    # THE CHECK: Is the vehicle still waiting for ME specifically?
    if not (
        pipeline_data.get("pipeline_status") == "ASSIGNED_BY_ENGAGEMENT_AGENT" # New status
        and pipeline_data.get("celery_task_id") == my_task_id
    ):
        print(
            f"Task {my_task_id}: ABORTING. Task is stale or has been superseded. "
            f"Vehicle {vehicle_id} has been reset or assigned a new task."
        )
        # You might want to call a /fail endpoint for engagement task here if stale
        return # Silently exit without doing any work

    # --- END OF VERIFICATION STEP ---

    print(f"Task {my_task_id}: Pre-execution check passed. Generating engagement message for {vehicle_id}.")

    # Fetching prediction
    print("  ▶ Fetching prediction...")
    pred_resp = get(f"{GET_VEHICLE_PREDICTION}/{vehicle_id}")
    pred = pred_resp.json().get("data") if pred_resp.status_code == 200 else None

    if not pred:
        print("  ❌ Prediction missing, skipping engagement")
        # Fail the engagement job
        return
    
    issues = extract_7d_top_issues_celery(vehicle_id=vehicle_id, features_snapshot=pred["features_snapshot"])
    print("  ✔ Prediction received")

    # Fetching booking
    print("  ▶ Fetching booking...")
    booking_resp = get(f"{GET_VEHICLE_SCHEDULE}/{vehicle_id}")
    booking = booking_resp.json().get("data") if booking_resp.status_code == 200 else None

    if not booking:
        print("  ❌ Booking missing or expired, skipping engagement")
        # Fail the engagement job
        return
    print("  ✔ Booking received")

    # Generating engagement message
    print("  ▶ Generating engagement message...")
    message_text = ""
    try:
        # The original code had `raise ValueError("ABCD")` - removing it for actual CrewAI execution
        crew_output = run_crewai_engagement_celery(vehicle_id, issues, booking)
        result = crew_output.tasks_output[0]
        message_text = result.raw or result.output # Accessing output
        print("  ✔ Message generated (CrewAI)")
    except Exception as e:
        print(f"❌ CrewAI agent failed, trying mock llm for {vehicle_id}: {e}")
        mock_response = mock_llm_engagement_response_celery(vehicle_id=vehicle_id, prediction=pred, booking=booking)
        message_text = mock_response["content"]
        print("  ✔ Message generated (Mock LLM)")

    # Sending email
    print("  ▶ Sending email...")
    try:
        send_email(
            to_email="customer@example.com", # Hardcoded email, might need to be dynamic
            subject="Important Update About Your Vehicle",
            body=message_text
        )
        print("  ✔ Email sent")
    except Exception as e:
        print(f"  ❌ Email failed: {e}")
        # Fail the engagement job
        return

    # Logging engagement
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

    # Updating vehicle workflow state
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
            "risk_state": risk_state # Pass original risk_state through
        }
    )
    print(f"[ENGAGEMENT TASK] ✅ Completed for {vehicle_id}")

    return f"Completed engagement for vehicle {vehicle_id}"