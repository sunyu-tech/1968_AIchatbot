# D:\github\1968_SMART_CHAT_BACK\services\incidents_service.py
import time
from typing import Dict, List, Optional, Tuple, Any

# 相容載入 config：支援 INCIDENT_CACHE_TTL_SEC 或舊名 CACHE_TTL_SEC
from core import config as CFG
from core.http_client import http_get
from parsers.incidents_parser import parse_incident_xml
from models.incidents import Incident

INCIDENT_ENDPOINTS: Dict[str, str] = getattr(CFG, "INCIDENT_ENDPOINTS", {})
INCIDENT_CACHE_TTL_SEC: int = int(getattr(CFG, "INCIDENT_CACHE_TTL_SEC",
                                          getattr(CFG, "CACHE_TTL_SEC", 45)))

# -----------------------------
# 記憶體快取：同一區資料在 TTL 內不重抓
# -----------------------------
_cache: Dict[str, Tuple[float, List[Incident]]] = {}

def _now() -> float:
    return time.time()

def _hit_cache(region: str) -> Optional[List[Incident]]:
    rec = _cache.get(region)
    if not rec:
        return None
    ts, data = rec
    if _now() - ts <= INCIDENT_CACHE_TTL_SEC:
        return data
    return None

def _set_cache(region: str, data: List[Incident]):
    _cache[region] = (_now(), data)

# -----------------------------
# 抓取 XML 並解析
# -----------------------------
def fetch_region(region: str) -> List[Incident]:
    region = (region or "").lower()
    hit = _hit_cache(region)
    if hit is not None:
        return hit
    url = INCIDENT_ENDPOINTS.get(region)
    if not url:
        return []
    r = http_get(url)
    r.raise_for_status()
    data = parse_incident_xml(r.text, region)
    _set_cache(region, data)
    return data

def fetch_all_regions() -> List[Incident]:
    out: List[Incident] = []
    for region in INCIDENT_ENDPOINTS.keys():
        try:
            out.extend(fetch_region(region))
        except Exception:
            # 個別區域壞掉不影響整體
            pass
    return out

# -----------------------------
# 過濾與格式化（只依 LLM filters）
# -----------------------------
def _place_blob(it: Incident) -> str:
    raw = it.raw or {}
    return " ".join([
        it.location or "",
        str(raw.get("interchange") or ""),
        str(raw.get("inc_location") or "")
    ])

def _normalize_exit_core(s: str) -> str:
    if not s:
        return ""
    return s.replace("交流道", "").replace("出口", "").strip()

def _exit_variants(s: str) -> List[str]:
    """
    產生出口名稱的幾種變體，提升命中機率。
    例如「五股出口」→ ["五股出口","五股交流道","五股"]
    """
    if not s:
        return []
    s = s.strip()
    core = _normalize_exit_core(s)
    vs = {s}
    if "交流道" in s:
        vs.add(s.replace("交流道", "出口"))
    if "出口" in s:
        vs.add(s.replace("出口", "交流道"))
    if core:
        vs.add(core)
    return list(vs)

def filter_incidents(items: List[Incident], cond: Dict[str, Any]) -> List[Incident]:
    def ok(it: Incident) -> bool:
        if cond.get("itype") and it.type != cond["itype"]:
            return False
        if cond.get("region") and it.region != cond["region"]:
            return False
        if cond.get("road"):
            if not (it.road and cond["road"].replace(" ", "") in it.road.replace(" ", "")):
                return False
        if cond.get("direction"):
            if not (it.direction and cond["direction"] in it.direction):
                return False
        # 出口：接受 「五股出口 / 五股交流道 / 五股」
        if cond.get("exit"):
            blob = _place_blob(it)
            if not any(v in blob for v in _exit_variants(cond["exit"])):
                return False
        # 多地名：任一命中即可
        places = cond.get("places") or []
        if places:
            blob = _place_blob(it)
            if not blob or not any(p in blob for p in places):
                return False
        return True

    return [x for x in items if ok(x)]

def _rank(hits: List[Incident]) -> None:
    def score(it: Incident) -> int:
        s = 0
        if it.road: s += 3
        if it.direction: s += 2
        if it.km: s += 2
        if it.type and it.type != "unknown": s += 1
        return -s
    hits.sort(key=score)

def _fmt(it: Incident) -> str:
    tmap = {"accident": "事故", "construction": "施工", "exit_congestion": "出口壅塞", "unknown": "事件"}
    title = tmap.get(it.type, "事件")
    road = it.road or "（未標示道路）"
    dire = f" {it.direction}" if it.direction else ""
    km   = f" @ {it.km}" if it.km else ""
    loc  = f"｜{it.location}" if it.location else ""
    ts   = f"（{it.start_time} 起）" if it.start_time else ""
    return f"• {title}｜{road}{dire}{km}{loc}{ts}"

# -----------------------------
# 條件逐級放寬：exit → places → direction → road → region
# -----------------------------
def _relax_filters_and_search(pool: List[Incident], cond_in: Dict[str, Any]) -> Tuple[List[Incident], Dict[str, Any], List[str]]:
    """
    依序移除條件：exit → places → direction → road → region，直到有資料或全移除。
    回傳 (hits, 使用的條件, 放寬了哪些鍵列表)
    """
    order = ["exit", "places", "direction", "road", "region"]

    # 先試原始條件
    hits = filter_incidents(pool, cond_in)
    _rank(hits)
    if hits:
        return hits, cond_in, []

    # 逐步放寬
    for i in range(len(order)):
        cond = {
            "itype": cond_in.get("itype"),
            "region": cond_in.get("region"),
            "road": cond_in.get("road"),
            "direction": cond_in.get("direction"),
            "exit": cond_in.get("exit"),
            "places": list(cond_in.get("places") or []),
        }
        for j in range(i + 1):
            key = order[j]
            if key == "places":
                cond["places"] = []
            else:
                cond[key] = None
        hits = filter_incidents(pool, cond)
        _rank(hits)
        if hits:
            return hits, cond, order[:i+1]

    # 全放寬也沒有
    return [], cond_in, order

# -----------------------------
# 對外主函式（只吃 LLM filters）
# -----------------------------
def query_incidents_by_filters(filters: Dict[str, Any], limit: int = 5):
    cond = {
        "itype":     (filters.get("type") or "").strip() or None,
        "region":    (filters.get("region") or "").strip() or None,
        "road":      (filters.get("road") or "").strip() or None,
        "direction": (filters.get("direction") or "").strip() or None,
        "exit":      (filters.get("exit") or "").strip() or None,
        "places":    filters.get("places") or [],
    }

    try:
        pool = fetch_region(cond["region"]) if cond["region"] else fetch_all_regions()
    except Exception:
        pool = []

    # ✅ 若完全沒有任何條件，就不要回固定清單
    if not any([cond["itype"], cond["region"], cond["road"], cond["direction"], cond["exit"], cond["places"]]):
        return {
            "conditions": cond,
            "count": 0,
            "items": [],
            "summary": "要幫你更精準查詢，請提供「道路（例：國道3號）＋方向（例：南下）＋地點/交流道（例：霧峰、南投）」其中至少一項。",
            "need_more": True,
            "ask": ["請補充：道路/方向/交流道或地名"]
        }

    hits, used_cond, relaxed_keys = _relax_filters_and_search(pool, cond)

    if not hits:
        return {
            "conditions": used_cond,
            "count": 0,
            "items": [],
            "summary": "目前查無符合條件的事件。可再提供更明確的里程、交流道或方向。",
            "need_more": True,
            "ask": ["是否有更精確的里程或交流道？"]
        }

    prefix = ""
    if relaxed_keys:
        zh = {"exit":"出口","places":"地名","direction":"方向","road":"道路","region":"區域"}
        keys_txt = "、".join(zh[k] for k in relaxed_keys if k in zh)
        prefix = f"（已放寬：{keys_txt}）\n"

    summary = prefix + "\n".join(_fmt(x) for x in hits[:limit])
    return {
        "conditions": used_cond,
        "count": len(hits),
        "items": hits[:limit],
        "summary": summary,
        "need_more": False,
        "ask": []
    }