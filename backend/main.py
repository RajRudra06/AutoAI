from fastapi import FastAPI

from backend.middleware.auth import AgentAuthMiddleware
from backend.routes.telemetry import router as telemetry_router
from backend.routes.predict import router as predict_router
from backend.routes.schedule import router as schedule_router
from backend.routes.feedback import router as feedback_router
from backend.routes.ueba import router as ueba_router
from backend.routes.vehicle_state import router as vehicle_state_router
from backend.routes.put_diagnosis_job import router as diagnosis_router
from backend.routes.put_diagnosis import router as diag_job_queue
from backend.routes.put_done_diagnosis import router as diag_done_routes
from backend.routes.service import router as service_router
from backend.routes.engagement import router as engagement_router
from backend.routes.activity import router as activity_router

app = FastAPI(title="AutoAI Backend")

@app.get("/health")
def health():
    return {"status": "ok"}

protected_app = FastAPI()

protected_app.add_middleware(AgentAuthMiddleware)

protected_app.include_router(telemetry_router)
protected_app.include_router(predict_router)
protected_app.include_router(schedule_router)
protected_app.include_router(feedback_router)
protected_app.include_router(ueba_router)
protected_app.include_router(vehicle_state_router)
protected_app.include_router(diagnosis_router)
protected_app.include_router(diag_job_queue)
protected_app.include_router(diag_done_routes)
protected_app.include_router(service_router)
protected_app.include_router(engagement_router)
protected_app.include_router(activity_router)


app.mount("/api", protected_app)
