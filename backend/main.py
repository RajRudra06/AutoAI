from fastapi import FastAPI
from backend.routes.telemetry import router as telemetry_router
from backend.routes.predict import router as predict_router
from backend.routes.schedule import router as schedule_router
from backend.routes.feedback import router as feedback_router
from backend.routes.ueba import router as ueba_router

app = FastAPI(title="AutoAI Backend")

app.include_router(telemetry_router)
app.include_router(predict_router)
app.include_router(schedule_router)
app.include_router(feedback_router)
app.include_router(ueba_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
