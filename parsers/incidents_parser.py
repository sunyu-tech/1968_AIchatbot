# D:\github\1968_SMART_CHAT_BACK\parsers\incidents_parser.py
from xml.etree import ElementTree as ET
from typing import List
from models.incidents import Incident  # ← 絕對匯入

def safe_float(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", ""))
    except Exception:
        return None

def _node_to_flat_dict(node: ET.Element) -> dict:
    d = {k.lower(): v for k, v in node.attrib.items()}
    for ch in node:
        tag = (ch.tag or "").split('}')[-1].lower()
        text = (ch.text or "").strip()
        if tag in d and d[tag] and text:
            d[tag] = f"{d[tag]} | {text}"
        else:
            d[tag] = text
    return d

def _pick(d: dict, *cands):
    for c in cands:
        v = d.get(c)
        if v not in (None, ""):
            return v
    return None

def _fmt_km(meters: str):
    try:
        n = int(str(meters))
        if n <= 0:
            return None
        return f"{n//1000}K+{n%1000:03d}"
    except Exception:
        return None

def _road_from_ids(freeway_id: str, expressway_id: str):
    # 國道優先，其次台xx線（快速公路/省道）
    if freeway_id and freeway_id != "0":
        return f"國道{int(freeway_id)}號"
    if expressway_id and expressway_id != "0":
        return f"台{int(expressway_id)}線"
    return None

def _direction_from_id(direction_id: str):
    # 依交通單位慣例：
    # 1: 東行 / 2: 西行 / 3: 南下 / 4: 北上
    m = str(direction_id or "").strip()
    return {"1": "東行", "2": "西行", "3": "南下", "4": "北上"}.get(m)

def _guess_type(d: dict) -> str:
    t = (d.get("inc_type_name") or "").strip()
    n = (d.get("inc_name") or "").strip()
    interchange = (d.get("interchange") or "")
    blob = f"{t} {n} {interchange}"

    # 施工
    if ("施工" in t) or ("施工" in n):
        return "construction"

    # 事故
    if ("事故" in t) or ("事故" in n) or ("車禍" in n) or ("追撞" in n) or ("翻覆" in n):
        return "accident"

    # 封閉預告 → 若含入口/出口，視為出口壅塞；否則歸到施工
    if ("封閉" in t) or ("封閉" in n):
        if ("入口" in interchange) or ("出口" in interchange):
            return "exit_congestion"
        return "construction"

    # 出口壅塞關鍵
    if ("壅塞" in t) or ("壅塞" in n):
        return "exit_congestion"
    if ("出口" in interchange) and ("封閉" not in n):
        return "exit_congestion"

    return "unknown"

def parse_incident_xml(xml_text: str, region: str) -> List[Incident]:
    root = ET.fromstring(xml_text)
    items = []
    rows = root.findall(".//incident") or root.findall(".//item")
    for node in rows:
        d = _node_to_flat_dict(node)

        freeway_id    = _pick(d, "freewayid")
        expressway_id = _pick(d, "expresswayid")
        direction_id  = _pick(d, "directionid")

        road = _road_from_ids(freeway_id, expressway_id)
        direction = _direction_from_id(direction_id)

        km_from = _fmt_km(_pick(d, "from_milepost"))
        km_to   = _fmt_km(_pick(d, "to_milepost"))
        km = None
        if km_from and km_to and km_from != km_to:
            km = f"{km_from}～{km_to}"
        else:
            km = km_from or km_to

        location = _pick(d, "interchange") or _pick(d, "inc_location") or _pick(d, "location")

        items.append(Incident(
            id=_pick(d, "incidentid", "id"),
            region=region,
            type=_guess_type(d),
            road=road,
            direction=direction,
            location=location,
            start_time=_pick(d, "inc_time", "starttime"),
            end_time=_pick(d, "inc_end_time", "endtime"),
            km=km,
            lat=safe_float(_pick(d, "latitude", "lat", "y", "gpsy")),
            lon=safe_float(_pick(d, "longitude", "lon", "x", "gpsx")),
            raw=d
        ))
    return items

def safe_float(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", ""))
    except Exception:
        return None
