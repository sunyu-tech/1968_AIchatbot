# D:\github\1968_SMART_CHAT_BACK\routers\traffic_incidents.py
from fastapi import APIRouter, Query
from core.intent_router import route_question
from services.incidents_service import query_incidents_by_filters

router = APIRouter(prefix="/traffic", tags=["traffic"])

@router.get("/incidents")
async def incidents(q: str = Query(..., description="自然語句：如『國道1號南下出口壅塞』"),
                    limit: int = 5):
    route, filters, _ = await route_question(q)
    if route != "incidents":
        # 若 LLM 沒判到 incidents，但使用者就是問路況，直接補一次關鍵字引導
        filters = {**filters, "type": filters.get("type","")}
    return query_incidents_by_filters(filters, limit=limit)
