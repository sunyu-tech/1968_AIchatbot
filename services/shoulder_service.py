# 開放路肩（以 eqId / uniqueId 對應）D:\github\1968_SMART_CHAT_BACK\services\shoulder_service.py
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
from core.http_client import http_get
from core.config import SCS_OP_URL, SCS_CFG_URL

CACHE_TTL_SEC = 30
_cache_op: Tuple[float, List[Dict]] = (0.0, [])
_cache_cfg: Tuple[float, List[Dict]] = (0.0, [])

def _now() -> float: return time.time()

def _hit(cache) -> Optional[List[Dict]]:
    ts, data = cache
    return data if (data and _now() - ts <= CACHE_TTL_SEC) else None

def _set(cache_name: str, data: List[Dict]):
    global _cache_op, _cache_cfg
    if cache_name == "op":
        _cache_op = (_now(), data)
    else:
        _cache_cfg = (_now(), data)

def _parse_op() -> List[Dict]:
    r = http_get(SCS_OP_URL); r.raise_for_status()
    root = ET.fromstring(r.content)
    out: List[Dict] = []
    for scsbox in root.findall(".//{*}ScsStatusData"):
        for scs in list(scsbox):
            if (scs.tag or "").split("}")[-1].lower() != "scs":
                continue
            out.append({
                "eqId": scs.attrib.get("eqId",""),
                "message": scs.attrib.get("message",""),
                "time": root.attrib.get("time","")
            })
    return out

def _parse_cfg() -> List[Dict]:
    r = http_get(SCS_CFG_URL); r.raise_for_status()
    root = ET.fromstring(r.content)
    out: List[Dict] = []
    for scsbox in root.findall(".//{*}scs_data"):
        for scs in list(scsbox):
            if (scs.tag or "").split("}")[-1].lower() != "scs":
                continue
            out.append({
                "uniqueId": scs.attrib.get("uniqueId",""),
                "freewayId": scs.attrib.get("freewayId",""),
                "expresswayId": scs.attrib.get("expresswayId",""),
                "directionId": scs.attrib.get("directionId",""),
                "milepost": scs.attrib.get("milepost",""),
            })
    return out

def fetch_scs_operation() -> List[Dict]:
    hit = _hit(_cache_op)
    if hit is not None: return hit
    data = _parse_op(); _set("op", data); return data

def fetch_scs_config() -> List[Dict]:
    hit = _hit(_cache_cfg)
    if hit is not None: return hit
    data = _parse_cfg(); _set("cfg", data); return data

def _dir_name(did: str) -> str:
    return {"1":"東行","2":"西行","3":"南下","4":"北上"}.get(str(did), "—")

def summarize_scs(limit: int = 10) -> str:
    ops = fetch_scs_operation()
    cfg = fetch_scs_config()
    cfg_map = {c.get("uniqueId",""): c for c in cfg if c.get("uniqueId")}
    if not ops and not cfg:
        return "目前查無開放路肩資料。"

    lines = []
    for it in ops[:limit]:
        uid = it.get("eqId","")
        c = cfg_map.get(uid, {})
        road = ("國道" + c.get("freewayId")) if (c.get("freewayId") and c.get("freewayId") != "0") else (("台" + c.get("expresswayId") + "線") if c.get("expresswayId") and c.get("expresswayId") != "0" else "（未標示道路）")
        dire = _dir_name(c.get("directionId",""))
        km = c.get("milepost")
        km_txt = f"{int(km)//1000}K+{int(km)%1000:03d}" if (km and km.isdigit()) else "—"
        msg = it.get("message") or "—"
        ts  = it.get("time") or ""
        lines.append(f"• {road} {dire} @ {km_txt}｜狀態：{msg}{('｜' + ts) if ts else ''}")
    return "\n".join(lines)
