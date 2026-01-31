to run BE: (run from root - AutoAI)
    uvicorn backend.main:app --reload
    python3 ./run_sys.py


The correct order to run the system

You need all three processes running:

Terminal 1 – FastAPI backend
PYTHONPATH=. uvicorn backend.main:app --reload

Terminal 2 – Simulator (creates telemetry)
PYTHONPATH=. python ./agents/collector_agent.py

Terminal 3 – Master agent (creates jobs)
PYTHONPATH=. python agents/master_agent.py

Terminal 4 – Diagnosis agent (processes jobs)
PYTHONPATH=. python agents/diagnosis_agent.py

Terminal 5 -  Scheduling agent (schedules diagosed jobs)
PYTHONPATH=. python agents/scheduling_agent.py

Terminal 6 - Engagement agent (customer engage)
PYTHONPATH=. python agents/engagement_agent.py

Terminal 7 - Service Completion (complete the lifecycle)
PYTHONPATH=. python agents/service_completion_agent.py

If any one is missing → diagnosis agent waits forever.

IDEAS:

* For now each agent is polling and not event driven architecture is there, and also since each agent is converted into class based system but it is not being used as class based since it is still one instance for all vehicle so high sequentiality nature of the entire flow

* To mitigate this we can have either thread based system where master pulls each vehicle and see which one needs to go thru lifecycle if required new Orchestrator thread is created whcih create their own thread of each agent and runs the entire lifecycle.

* Other thread method could be master initiates one diagnosis thread and before dying this diagnosis agent instantiate next agent required and this goes till vehicle is out of lifecycle 

* But for both these u cant have lets say more than 50-100 threads since that will choke the system so thread pool will be used 

* Another approach is to go with celery+redis and event driver architecture 

* For demo add metric end point to store each step and uses crewai to write a rapport for showing it to the user what happened at each step.

* Celery + redis workings:

1. redis is the queue holder for the the task list and act as the medium before task is picked by the celery.

2. celery has one main app file where the entire celery config are made and multiple task files made seprately containing all the task u want to run asyncly.

3. as many as workers can be run u want that will actually pick the task avaible not attached to one particular task