# 公路局即時路段D:\github\1968_SMART_CHAT_BACK\services\thb_service.py
# 公路局即時路段（目前暫停）
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
from core.http_client import http_get

DISABLED = True  # ← 暫停旗標

THB_LIVE_URL = "https://thbtrafficapp.thb.gov.tw/opendata/section/livetrafficdata/LiveTrafficList.xml"
CACHE_TTL_SEC = 30
_cache: Tuple[float, List[Dict]] = (0.0, [])

def _now() -> float: return time.time()
def _hit_cache() -> Optional[List[Dict]]:
    ts, data = _cache
    return data if (data and _now() - ts <= CACHE_TTL_SEC) else None
def _set_cache(data: List[Dict]) -> None:
    global _cache; _cache = (_now(), data)

def fetch_thb_live() -> List[Dict]:
    if DISABLED:
        return []  # 暫停時直接回空集合
    hit = _hit_cache()
    if hit is not None: return hit
    r = http_get(THB_LIVE_URL); r.raise_for_status()
    root = ET.fromstring(r.content)
    out: List[Dict] = []
    for node in root.findall(".//{*}LiveTraffic"):
        rec: Dict[str, str] = {}
        for ch in list(node):
            tag = (ch.tag or "").split("}")[-1]
            rec[tag] = (ch.text or "").strip()
        rec["SectionID"]   = rec.get("SectionID","")
        rec["TravelTime"]  = rec.get("TravelTime","")
        rec["TravelSpeed"] = rec.get("TravelSpeed","") or rec.get("Speed","")
        rec["Congestion"]  = rec.get("CongestionLevel","") or rec.get("Congestion","")
        rec["UpdateTime"]  = rec.get("DataCollectTime","") or rec.get("UpdateTime","")
        out.append(rec)
    _set_cache(out)
    return out

def summarize_thb(limit: int = 10) -> str:
    if DISABLED:
        return "（公路局即時路段功能暫停）"
    items = fetch_thb_live()
    if not items: return "目前查無公路局即時路段資料。"
    lines = []
    for it in items[:limit]:
        sid = it.get("SectionID") or "（未標示路段）"
        spd = it.get("TravelSpeed") or "—"
        cong = it.get("Congestion") or "—"
        t = it.get("UpdateTime") or ""
        lines.append(f"• {sid}｜速率：{spd} km/h｜壅塞：{cong}{('｜' + t) if t else ''}")
    return "\n".join(lines)
