# 替代道路 / 旅行時間（新版 schema）D:\github\1968_SMART_CHAT_BACK\services\alt_routes_service.py
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
from core.http_client import http_get
from core.config import ALT_ROUTES_URL

CACHE_TTL_SEC = 60
_cache: Tuple[float, List[Dict]] = (0.0, [])

def _now() -> float: return time.time()

def _hit_cache() -> Optional[List[Dict]]:
    ts, data = _cache
    if data and _now() - ts <= CACHE_TTL_SEC:
        return data
    return None

def _set_cache(data: List[Dict]) -> None:
    global _cache
    _cache = (_now(), data)

def fetch_alt_routes() -> List[Dict]:
    hit = _hit_cache()
    if hit is not None:
        return hit

    r = http_get(ALT_ROUTES_URL); r.raise_for_status()
    root = ET.fromstring(r.content)

    out: List[Dict] = []
    for node in list(root):
        tag = (node.tag or "").split("}")[-1]
        if tag.lower() != "traffic":
            continue
        rec = {
            "Group": node.attrib.get("group_label",""),
            "Alternative": node.attrib.get("alternative",""),
            "Direction": node.attrib.get("direction",""),
            "TravelTimeSec": node.attrib.get("travel_time",""),
            "AreaType": node.attrib.get("area_type",""),
            "UpdateTime": node.attrib.get("data_time",""),
        }
        out.append(rec)

    _set_cache(out)
    return out

def summarize_alt_routes(limit: int = 8) -> str:
    items = fetch_alt_routes()
    if not items:
        return "目前查無替代道路/旅行時間資料。"
    lines = []
    for it in items[:limit]:
        sec = it.get("Group") or "（未標示群組）"
        alt = it.get("Alternative") or "—"
        dire = it.get("Direction") or "—"
        tsec = it.get("TravelTimeSec")
        mins = f"{int(int(tsec)/60)} 分" if (tsec and tsec.isdigit()) else "—"
        ts = it.get("UpdateTime") or ""
        area = it.get("AreaType") or ""
        lines.append(f"• {sec}｜建議替代：{alt}｜方向：{dire}｜旅行時間：{mins}{('｜' + area) if area else ''}{('｜' + ts) if ts else ''}")
    return "\n".join(lines)
