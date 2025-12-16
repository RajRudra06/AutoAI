from fastapi import FastAPI

from backend.middleware.auth import AgentAuthMiddleware
from backend.routes.telemetry import router as telemetry_router
from backend.routes.predict import router as predict_router
from backend.routes.schedule import router as schedule_router
from backend.routes.feedback import router as feedback_router
from backend.routes.ueba import router as ueba_router

# ----------------------------
# Public app (NO middleware)
# ----------------------------
app = FastAPI(title="AutoAI Backend")

@app.get("/health")
def health():
    return {"status": "ok"}

# ----------------------------
# Protected sub-app
# ----------------------------
protected_app = FastAPI()

protected_app.add_middleware(AgentAuthMiddleware)

protected_app.include_router(telemetry_router)
protected_app.include_router(predict_router)
protected_app.include_router(schedule_router)
protected_app.include_router(feedback_router)
protected_app.include_router(ueba_router)

# ----------------------------
# Mount protected app
# ----------------------------
app.mount("/api", protected_app)
