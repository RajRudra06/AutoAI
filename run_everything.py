#!/usr/bin/env python3
"""One-command runtime launcher for AutoAI backend, agents, and Celery workers."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

import certifi
import requests
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parent
PYTHON_BIN = ROOT / "AutoAI_ENV" / "bin" / "python"


def build_env() -> dict[str, str]:
    env = os.environ.copy()

    config = dotenv_values(ROOT / "backend" / ".env")
    for key, value in config.items():
        if value is not None:
            env[key] = value

    env.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
    env.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    env.setdefault("BACKEND_API_URL", "http://127.0.0.1:8000")

    env["PYTHONPATH"] = "."
    env["SSL_CERT_FILE"] = certifi.where()

    return env


def clean_stale_processes() -> None:
    patterns = [
        "uvicorn backend.main:app",
        "agents/collector_agent.py",
        "agents/master_agent.py",
        "agents/diagnosis_agent.py",
        "agents/scheduling_agent.py",
        "agents/engagement_agent.py",
        "agents/service_completion_agent.py",
        "-m celery -A worker_tasks.celery_config worker",
    ]

    for pattern in patterns:
        subprocess.run(["pkill", "-f", pattern], cwd=ROOT, check=False)

    time.sleep(1)


def wait_for_backend(env: dict[str, str], backend_proc: subprocess.Popen, timeout_seconds: int = 90) -> bool:
    base_url = env.get("BACKEND_API_URL", "http://127.0.0.1:8000")
    health_url = f"{base_url}/health"

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if backend_proc.poll() is not None:
            print(f"[LAUNCHER][ERROR] Backend process exited early with code {backend_proc.returncode}")
            return False

        try:
            response = requests.get(health_url, timeout=3)
            if response.status_code == 200:
                print(f"[LAUNCHER] Backend is healthy at {health_url}")
                return True
        except Exception:
            pass
        time.sleep(2)

    return False


def start_process(label: str, cmd: List[str], env: dict[str, str]) -> subprocess.Popen:
    print(f"[LAUNCHER] Starting {label}: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env)
    return proc


def main() -> int:
    if not PYTHON_BIN.exists():
        print(f"[LAUNCHER][ERROR] Missing interpreter: {PYTHON_BIN}")
        return 1

    env = build_env()
    clean_stale_processes()

    processes: List[Tuple[str, subprocess.Popen]] = []

    try:
        backend_cmd = [str(PYTHON_BIN), "-m", "uvicorn", "backend.main:app", "--port", "8000", "--reload", "--reload-dir", "backend"]
        backend = start_process("backend", backend_cmd, env)
        processes.append(("backend", backend))

        if not wait_for_backend(env, backend):
            print("[LAUNCHER][ERROR] Backend did not become healthy in time.")
            return 1

        startup_plan = [
            ("collector_agent", [str(PYTHON_BIN), "agents/collector_agent.py"]),
            ("master_agent", [str(PYTHON_BIN), "agents/master_agent.py"]),
            (
                "worker_diagnosis_queue",
                [
                    str(PYTHON_BIN),
                    "-m",
                    "celery",
                    "-A",
                    "worker_tasks.celery_config",
                    "worker",
                    "-l",
                    "info",
                    "-Q",
                    "diagnosis_queue",
                    "-n",
                    "diagnosis_queue_worker@%h",
                ],
            ),
            ("diagnosis_agent", [str(PYTHON_BIN), "agents/diagnosis_agent.py"]),
            (
                "worker_execution_diagnosis_queue",
                [
                    str(PYTHON_BIN),
                    "-m",
                    "celery",
                    "-A",
                    "worker_tasks.celery_config",
                    "worker",
                    "-l",
                    "info",
                    "-Q",
                    "execution_diagnosis_task_queue",
                    "-n",
                    "execution_diagnosis_queue_worker@%h",
                ],
            ),
            ("scheduling_agent", [str(PYTHON_BIN), "agents/scheduling_agent.py"]),
            (
                "worker_scheduling_queue",
                [
                    str(PYTHON_BIN),
                    "-m",
                    "celery",
                    "-A",
                    "worker_tasks.celery_config",
                    "worker",
                    "-l",
                    "info",
                    "-Q",
                    "scheduling_queue",
                    "-n",
                    "scheduling_queue_worker@%h",
                ],
            ),
            ("engagement_agent", [str(PYTHON_BIN), "agents/engagement_agent.py"]),
            (
                "worker_engagement_queue",
                [
                    str(PYTHON_BIN),
                    "-m",
                    "celery",
                    "-A",
                    "worker_tasks.celery_config",
                    "worker",
                    "--loglevel=info",
                    "--pool=threads",
                    "--concurrency=4",
                    "--queues=engagement_queue",
                    "-n",
                    "engagement_queue_worker@%h",
                ],
            ),
            ("service_completion_agent", [str(PYTHON_BIN), "agents/service_completion_agent.py"]),
            (
                "worker_service_completion_queue",
                [
                    str(PYTHON_BIN),
                    "-m",
                    "celery",
                    "-A",
                    "worker_tasks.celery_config",
                    "worker",
                    "-l",
                    "info",
                    "-Q",
                    "service_completion_queue",
                    "-n",
                    "service_completion_queue_worker@%h",
                ],
            ),
        ]

        for label, cmd in startup_plan:
            proc = start_process(label, cmd, env)
            processes.append((label, proc))
            time.sleep(1.2)

        print("[LAUNCHER] All services started. Press Ctrl+C to stop all.")

        while True:
            dead = [(label, proc.returncode) for label, proc in processes if proc.poll() is not None]
            if dead:
                for label, code in dead:
                    print(f"[LAUNCHER][WARN] {label} exited with code {code}")
                print("[LAUNCHER] Stopping all remaining processes due to unexpected exit.")
                break
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n[LAUNCHER] Ctrl+C received. Shutting down all services...")
    finally:
        for label, proc in reversed(processes):
            if proc.poll() is None:
                try:
                    proc.send_signal(signal.SIGTERM)
                except Exception:
                    pass
        time.sleep(1.5)
        for label, proc in reversed(processes):
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("[LAUNCHER] Shutdown complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
