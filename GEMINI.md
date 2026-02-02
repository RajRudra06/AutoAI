# GEMINI - AutoAI Project Context

This document provides a comprehensive overview of the AutoAI project for the Gemini CLI, detailing its architecture, how to run it, and key development conventions.

## Project Overview

AutoAI is a proactive vehicle maintenance system designed as a multi-agent ecosystem. It simulates the collection of vehicle telemetry, uses a machine learning model to predict failures, and manages the subsequent diagnosis and service workflow.

The architecture consists of several key components:

*   **FastAPI Backend (`backend/`):** A central API server that acts as the backbone for the system. It handles data ingestion, state management for vehicles and jobs, and provides endpoints for the various agents to communicate.

*   **Data Collector Agent (`agents/collector_agent.py`):** Simulates a vehicle's onboard device. It generates raw telemetry data, extracts features, and sends them to the FastAPI backend.

*   **Master Agent (`agents/master_agent.py`):** The primary orchestrator. It periodically fetches the state of all vehicles from the backend, evaluates them against a health gate (`helpers/logic/health_gate.py`), and creates diagnosis jobs for vehicles that require attention.

*   **Diagnosis Agent (`agents/diagnosis_agent.py`):** The predictive component. It polls for diagnosis jobs created by the Master Agent, executes a pre-trained Isolation Forest model (`diag_agent_model/iForest/models/isolation_forest_v1.pkl`) to detect anomalies, and reports the diagnosis results back to the backend.

*   **Celery Integration (`tasks_celery/`):** The project includes a setup for Celery with a Redis broker. This indicates a planned or in-progress migration from the current polling-based architecture to a more efficient, event-driven one.

*   **Other Agents:** The system includes other agents (`scheduling_agent.py`, `engagement_agent.py`, etc.) that handle subsequent steps in the vehicle service lifecycle.

## Building and Running

The system requires multiple components to be running simultaneously. Ensure you have a `.env` file at the root with the `BACKEND_API_URL` and Celery configuration.

**1. Install Dependencies:**

The project uses a virtual environment (`AutoAI_ENV`). There is no `requirements.txt` file, so dependencies must be inferred from the code and installed manually. Key dependencies include:
*   `fastapi`
*   `uvicorn`
*   `pandas`
*   `scikit-learn`
*   `joblib`
*   `python-dotenv`
*   `celery`
*   `redis`

**2. Run the System:**

Open multiple terminals and run the components in the following order. The `PYTHONPATH=.` prefix is crucial for correct module resolution.

*   **Terminal 1 – FastAPI Backend:**
    ```bash
    PYTHONPATH=. uvicorn backend.main:app --reload
    ```

*   **Terminal 2 – Data Collector (Simulator):**
    ```bash
    PYTHONPATH=. python agents/collector_agent.py
    ```

*   **Terminal 3 – Master Agent:**
    ```bash
    PYTHONPATH=. python agents/master_agent.py
    ```

*   **Terminal 4 – Diagnosis Agent:**
    ```bash
    PYTHONPATH=. python agents/diagnosis_agent.py
    ```

*   **Terminal 5+ – Other Agents:**
    Run the other agents as needed for the full lifecycle simulation (scheduling, engagement, etc.).
    ```bash
    PYTHONPATH=. python agents/scheduling_agent.py
    PYTHONPATH=. python agents/engagement_agent.py
    # ... and so on
    ```

## Development Conventions

*   **Architecture:** The system currently uses a polling-based architecture where agents repeatedly query the backend API. The presence of the `tasks_celery` directory strongly suggests a future direction towards an event-driven architecture.
*   **Configuration:** Configuration is managed via environment variables loaded from a `.env` file using `python-dotenv`.
*   **Communication:** Agents are stateless and communicate indirectly through the central FastAPI backend. They use a shared utility (`agents/utils/agent_api_client.py`) for making authenticated API calls.
*   **Machine Learning:** The core predictive logic resides in the Diagnosis Agent, which uses a `joblib`-serialized Isolation Forest model. The model and its feature engineering are separate from the main application logic.
*   **Testing:** There is no dedicated testing suite (`tests/` directory or `pytest` setup) in the project. The `backend/raw_data_generator.py` and `agents/collector_agent.py` act as a simulation framework for end-to-end testing.
*   **Code Style:** The code is generally structured into classes for each agent. There are no enforced linting or formatting configurations apparent.

## Future Enhancements / Roadmap

The following are the primary development goals for the AutoAI project:

1.  **Introduce Concurrency:** Transition from the current `while True` loop-based polling to a more concurrent execution model, likely leveraging the existing Celery integration.
2.  **Mature Agentic Decision Thinking:** Enhance the decision-making processes of the agents, focusing on more sophisticated logic without introducing excessive complexity.
3.  **Refine Layering:** Improve the architectural separation and interaction between the database, FastAPI backend, various agents, and the Celery task queue for increased robustness and maintainability.
4.  **Develop Frontend with Real-time Simulation:** Create a web-based frontend application that provides a real-time simulation of the vehicle maintenance lifecycle. This frontend will allow users (recruiters) to:
    *   Initiate a simulation with a "simulate" button.
    *   Observe real-time updates of vehicle status and agent activities via WebSockets.
    *   After a cycle completes, access a summary generated by a CrewAI agent that analyzes logs for that specific vehicle. This aims to showcase the project's complexity and agentic workflow.
