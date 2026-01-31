from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

app = Celery(
    'vehicle_health_system',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=[
        'diagnosis_tasks',
    ]
)

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
