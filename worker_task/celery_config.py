from celery import Celery
import os
from dotenv import load_dotenv
from kombu import Queue

load_dotenv()

app = Celery(
    'vehicle_health_system',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=[
        'worker_task.diagnosis_tasks',
        'worker_task.scheduling_tasks',
        'worker_task.engagement_tasks',
        'worker_task.service_completion_tasks'
    ]
)

app.conf.task_queues = (
    Queue('diagnosis_queue'),
    Queue('scheduling_queue'),
    Queue('engagement_queue'),
    Queue('service_completion_queue'),
    Queue('default')
)

app.conf.task_routes = {
     'diagnosis_tasks.*': {'queue': 'diagnosis_queue'},
     'scheduling_tasks.*': {'queue': 'scheduling_queue'},
     'engagement_tasks.*': {'queue': 'engagement_queue'},
     'service_completion_tasks.*': {'queue': 'service_completion_queue'},
    }

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_retry_backoff=True,
    task_retry_backoff_max=600,
    task_retry_jitter=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

print("[CELERY] App configured")