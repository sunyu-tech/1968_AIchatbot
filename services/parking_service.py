# 服務區停車位D:\github\1968_SMART_CHAT_BACK\services\parking_service.py
# 資料源: core.config.PARK_URL（統一由 endpoints 管）
# 功能: 解析各服務區可用車位；可依 LLM filters 的 parking_name 做過濾

import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
from core.http_client import http_get
from core.config import PARK_URL

CACHE_TTL_SEC = 60
_cache: Tuple[float, List[Dict]] = (0.0, [])

def _now() -> float: return time.time()

def _hit_cache() -> Optional[List[Dict]]:
    ts, data = _cache
    if data and _now() - ts <= CACHE_TTL_SEC: return data
    return None

def _set_cache(data: List[Dict]) -> None:
    global _cache
    _cache = (_now(), data)

def _strip_ns(tag: str) -> str:
    return (tag or "").split("}")[-1]

def fetch_parking() -> List[Dict]:
    hit = _hit_cache()
    if hit is not None:
        return hit
    r = http_get(PARK_URL); r.raise_for_status()
    root = ET.fromstring(r.content)

    items: List[Dict] = []
    pa_root = None
    for ch in list(root):
        if _strip_ns(ch.tag).lower() in ("parkingavailabilities", "parkingavailabilitylist", "parkinglist"):
            pa_root = ch
            break
    if pa_root is None:
        pa_root = root

    for node in list(pa_root):
        if _strip_ns(node.tag) != "ParkingAvailability":
            continue
        rec: Dict[str, str] = {}
        for ch in list(node):
            tag = _strip_ns(ch.tag)
            if tag == "CarParkName":
                for sub in list(ch):
                    if _strip_ns(sub.tag) == "Zh_tw":
                        rec["Name"] = (sub.text or "").strip()
            elif tag in ("TotalSpaces", "AvailableSpaces", "ServiceStatus", "FullStatus", "ChargeStatus", "DataCollectTime", "CarParkID"):
                rec[tag] = (ch.text or "").strip()
            elif tag == "Availabilities":
                for av in list(ch):
                    if _strip_ns(av.tag) != "Availability": continue
                    st = av.find(".//{*}SpaceType")
                    ns = av.find(".//{*}NumberOfSpaces")
                    asv = av.find(".//{*}AvailableSpaces")
                    key = (st.text if st is not None else "").strip()
                    rec[f"Type_{key}_Total"] = (ns.text if ns is not None else "").strip()
                    rec[f"Type_{key}_Avail"] = (asv.text if asv is not None else "").strip()
        if rec:
            items.append(rec)

    _set_cache(items)
    return items

def _norm_sa(s: str) -> str:
    return (s or "").replace("服務區", "").replace("臺","台").strip()

def summarize_parking(keyword: str = "", limit: int = 8) -> str:
    items = fetch_parking()
    if not items:
        return "目前查無服務區停車位資料。"
    if keyword:
        k = _norm_sa(keyword)
        cand = []
        for x in items:
            name = x.get("Name") or ""
            name_n = _norm_sa(name)
            # 完整包含或前綴/後綴近似都算
            if (k in name_n) or (name_n in k):
                cand.append(x)
        items = cand
    if not items:
        return f"找不到與「{keyword}」相符的服務區停車位資料。"

    lines = []
    for it in items[:limit]:
        name = it.get("Name") or "（未標示名稱）"
        total = it.get("TotalSpaces") or "—"
        avail = it.get("AvailableSpaces") or "—"
        t = it.get("DataCollectTime") or ""
        small = it.get("Type_1_Avail")
        coach = it.get("Type_2_Avail")
        moto  = it.get("Type_3_Avail")
        ev    = it.get("Type_10_Avail")
        extras = []
        if small is not None: extras.append(f"小客可用 {small}")
        if coach is not None: extras.append(f"大客可用 {coach}")
        if moto  is not None: extras.append(f"機車可用 {moto}")
        if ev    is not None: extras.append(f"電動車位可用 {ev}")
        extra_txt = ("｜" + "；".join(extras)) if extras else ""
        lines.append(f"• {name}｜可用 {avail}/{total}{extra_txt}{('｜' + t) if t else ''}")
    return "\n".join(lines)