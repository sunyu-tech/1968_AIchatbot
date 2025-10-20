# D:\github\1968_SMART_CHAT_BACK\core\geocoding.py
import os, re, requests
from functools import lru_cache

TW_VIEWBOX = "119.0,21.5,122.5,25.8"
_GKEY = os.getenv("GOOGLE_MAPS_KEY", "").strip()

def _strip_house_no(q: str) -> str:
    return re.sub(r"(?:\d+之?\d*)號?$", "", q).strip()

@lru_cache(maxsize=512)
def geocode(place: str):
    if not place:
        return None
    # 1) Google Maps（若有金鑰）
    if _GKEY:
        try:
            r = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                             params={"address": place, "region":"tw", "language":"zh-TW", "key":_GKEY},
                             timeout=6)
            js = r.json()
            if (js.get("results") or []):
                it = js["results"][0]
                loc = it["geometry"]["location"]
                label = it.get("formatted_address","")
                return loc["lat"], loc["lng"], label, "gmaps"
        except Exception:
            pass
    # 2) Nominatim（免金鑰）
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": place+" 台灣", "format":"json", "limit":1, "countrycodes":"tw",
                                 "addressdetails":1, "namedetails":1, "accept-language":"zh-TW",
                                 "bounded":1, "viewbox":TW_VIEWBOX},
                         headers={"User-Agent":"smartchat/1.0"}, timeout=6)
        arr = r.json()
        if not arr: return None
        it = arr[0]
        lat = float(it["lat"]); lon = float(it["lon"])
        namedetails = it.get("namedetails", {}) or {}
        raw_name = namedetails.get("name") or ""
        addr = it.get("address", {}) or {}
        city = addr.get("city") or addr.get("county") or ""
        road = addr.get("road") or addr.get("street") or addr.get("pedestrian") or ""
        house= addr.get("house_number") or ""
        if house and road and city:
            label = f"{city}{road}{house}"
        elif road and city:
            label = f"{city}{road}"
        else:
            label = raw_name or it.get("display_name") or place
        return lat, lon, label, "nominatim"
    except Exception:
        return None
