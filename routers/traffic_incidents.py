# D:\github\1968_SMART_CHAT_BACK\routers\traffic_incidents.py
from fastapi import APIRouter, Query
from typing import Optional
from ..services.incidents_service import query_incidents_by_question

router = APIRouter(prefix="/traffic", tags=["traffic"])

@router.get("/incidents")
def incidents(q: str = Query(..., description="自然語句：如『國道1號南下出口壅塞』"),
              limit: int = 5):
    return query_incidents_by_question(q, limit=limit)
