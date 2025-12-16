import subprocess
import sys
import os

#PYTHONPATH=. python backend/simulator.py
 

ENV = os.environ.copy()
ENV["PYTHONPATH"] = "."

processes = [
    [sys.executable, "backend/simulator.py"],
    [sys.executable, "agents/master_agent.py"],
    [sys.executable, "agents/diagnosis_agent.py"],
]

procs = []

try:
    for cmd in processes:
        print("Starting:", " ".join(cmd))
        procs.append(
            subprocess.Popen(
                cmd,
                env=ENV
            )
        )

    for p in procs:
        p.wait()

except KeyboardInterrupt:
    print("\nShutting down...")
    for p in procs:
        p.terminate()
