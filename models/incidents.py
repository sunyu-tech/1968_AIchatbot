# D:\github\1968_SMART_CHAT_BACK\models\incidents.py
from typing import Optional
from pydantic import BaseModel

class Incident(BaseModel):
    id: Optional[str] = None
    region: Optional[str] = None             # north/center/south
    type: Optional[str] = None               # accident/construction/exit_congestion/unknown
    road: Optional[str] = None               # 國道/省道名，如 "國道1號"
    direction: Optional[str] = None          # 南下/北上/順向/逆向...
    location: Optional[str] = None           # 文字描述
    start_time: Optional[str] = None         # ISO or source string
    end_time: Optional[str] = None
    km: Optional[str] = None                 # 里程，如 "71K+300"
    lat: Optional[float] = None
    lon: Optional[float] = None
    raw: Optional[dict] = None               # 全部欄位（備查）
