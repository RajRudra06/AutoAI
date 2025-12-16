to run BE: (run from root - AutoAI)
    uvicorn backend.main:app --reload
    python3 ./run_sys.py


The correct order to run the system

You need all three processes running:

Terminal 1 – FastAPI backend
PYTHONPATH=. uvicorn backend.main:app --reload

Terminal 2 – Simulator (creates telemetry)
PYTHONPATH=. python backend/simulator.py

Terminal 3 – Master agent (creates jobs)
PYTHONPATH=. python agents/master_agent.py

Terminal 4 – Diagnosis agent (processes jobs)
PYTHONPATH=. python agents/diagnosis_agent.py


If any one is missing → diagnosis agent waits forever.