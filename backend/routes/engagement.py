# backend/routers/engagement.py
from fastapi import APIRouter
from backend.db.connection import db

router = APIRouter(prefix="/engagement", tags=["Engagement"])

@router.post("/log")
def log_engagement(payload: dict):
    db.engagements.insert_one(payload)
    return {"success": True}
